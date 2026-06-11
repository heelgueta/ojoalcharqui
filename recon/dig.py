"""Recon pass 2: extract concrete API endpoints/keys from each store's frontend."""
import json
import re
import sys

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "es-CL,es;q=0.9",
}

INTERESTING = re.compile(
    r'https?://[a-z0-9\.\-]*(?:smdigital|instaleap|cencosud|unimarc|alvi|lider|walmart|tottus|falabella|acuenta|smu)[a-z0-9\.\-/_]*',
    re.I,
)
KEYS = re.compile(r'["\']?(x-api-key|apiKey|api_key|clientId|client_id|X-IL-Client)["\']?\s*[:=]\s*["\']([^"\']{8,80})["\']', re.I)


def grep(text, label, out):
    urls = set(INTERESTING.findall(text))
    keys = set(KEYS.findall(text))
    if urls or keys:
        out.setdefault(label, {})
        if urls:
            out[label]["urls"] = sorted(urls)[:40]
        if keys:
            out[label]["keys"] = sorted(keys)[:20]


def fetch(client, url):
    try:
        r = client.get(url)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def main():
    out = {}
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, verify=False) as c:
        for store, url in [
            ("jumbo", "https://www.jumbo.cl/"),
            ("santaisabel", "https://www.santaisabel.cl/"),
            ("lider", "https://www.lider.cl/supermercado"),
            ("unimarc", "https://www.unimarc.cl/"),
            ("alvi", "https://www.alvi.cl/"),
            ("acuenta", "https://www.acuenta.cl/"),
        ]:
            html = fetch(c, url)
            grep(html, f"{store}:html", out)
            # fetch first-party JS bundles and grep those too
            base = url.split("/", 3)
            origin = base[0] + "//" + base[2]
            scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
            seen = 0
            for s in scripts:
                if s.startswith("//"):
                    s = "https:" + s
                elif s.startswith("/"):
                    s = origin + s
                if any(d in s for d in ["googletag", "gtm", "facebook", "hotjar"]):
                    continue
                js = fetch(c, s)
                grep(js, f"{store}:js", out)
                seen += 1
                if seen >= 12:
                    break
            print(f"-- {store} done ({seen} js)", flush=True)
    with open("recon/dig.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out, indent=1, ensure_ascii=False)[:6000])


if __name__ == "__main__":
    sys.exit(main())
