"""Recon pass 3: find concrete product-listing API hosts inside JS bundles.

Greps the main JS bundles for full https hosts and graphql/rest path fragments,
then tries a few candidate product calls per platform family.
"""
import json
import re
import sys

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-CL,es;q=0.9",
    "Origin": "https://www.unimarc.cl",
    "Referer": "https://www.unimarc.cl/",
}

HOST = re.compile(r'https://([a-z0-9\-]+\.(?:smdigital\.cl|cencosud\.com|unimarc\.cl|alvi\.cl|lider\.cl|walmart\.com|instaleap\.io|algolia\.net|constructor\.io))', re.I)
PATHISH = re.compile(r'["\'](/(?:api|bff|graphql|catalog|v\d)[a-z0-9/_\-]{2,60})["\']', re.I)


def bundles_of(client, url, origin):
    html = client.get(url).text
    scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
    fixed = []
    for s in scripts:
        if s.startswith("//"):
            s = "https:" + s
        elif s.startswith("/"):
            s = origin + s
        if any(d in s for d in ["googletag", "gtm", "facebook", "hotjar", "cookielaw"]):
            continue
        fixed.append(s)
    return html, fixed[:15]


def main():
    out = {}
    targets = [
        ("jumbo", "https://www.jumbo.cl/", "https://www.jumbo.cl"),
        ("unimarc", "https://www.unimarc.cl/", "https://www.unimarc.cl"),
    ]
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=40, verify=False) as c:
        for store, url, origin in targets:
            hosts, paths = set(), set()
            html, bundles = bundles_of(c, url, origin)
            for b in [html] + bundles:
                txt = b if b.startswith("<") else (c.get(b).text if b.startswith("http") else "")
                hosts |= set(m.lower() for m in HOST.findall(txt))
                paths |= set(PATHISH.findall(txt))
            out[store] = {"hosts": sorted(hosts), "paths": sorted(paths)[:60]}
            print(f"== {store}\n hosts: {sorted(hosts)}\n paths: {sorted(paths)[:40]}\n", flush=True)
    with open("recon/endpoints.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
