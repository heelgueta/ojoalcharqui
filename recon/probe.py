"""Recon: fingerprint Chilean supermarket platforms.

Fetches each store's homepage with browser-grade headers, follows redirects,
and looks for platform fingerprints (VTEX, Algolia, Next.js BFFs, API keys
embedded in frontend JS). Output: recon/report.json
"""
import json
import re
import sys

import httpx

STORES = {
    "jumbo": "https://www.jumbo.cl/",
    "santaisabel": "https://www.santaisabel.cl/",
    "lider": "https://www.lider.cl/",
    "unimarc": "https://www.unimarc.cl/",
    "tottus": "https://www.tottus.cl/",
    "acuenta": "https://www.acuenta.cl/",
    "alvi": "https://www.alvi.cl/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

FINGERPRINTS = {
    "vtex": [r"vtex", r"vteximg\.com\.br", r"__RUNTIME__"],
    "algolia": [r"algolia", r"x-algolia-api-key", r"applicationId"],
    "nextjs": [r"__NEXT_DATA__", r"/_next/"],
    "smdigital": [r"smdigital", r"apijumboweb", r"apisantaisabelweb"],
    "instaleap": [r"instaleap"],
    "shopify": [r"cdn\.shopify"],
    "salesforce_cc": [r"demandware"],
    "react": [r"react"],
}

API_KEY_PATTERNS = [
    (r'x-api-key["\']?\s*[:=]\s*["\']([A-Za-z0-9\-_]{16,})', "x-api-key"),
    (r'apiKey["\']?\s*[:=]\s*["\']([A-Za-z0-9\-_]{16,})', "apiKey"),
    (r'algolia[^"\']{0,40}["\']([A-Za-z0-9]{32})["\']', "algolia-ish"),
]


def probe(name: str, url: str, client: httpx.Client) -> dict:
    out = {"store": name, "url": url}
    try:
        r = client.get(url)
        out["status"] = r.status_code
        out["final_url"] = str(r.url)
        out["server"] = r.headers.get("server", "")
        out["vtex_headers"] = {k: v for k, v in r.headers.items() if "vtex" in k.lower()}
        html = r.text[:800_000]
        out["platforms"] = sorted(
            p for p, pats in FINGERPRINTS.items()
            if any(re.search(pat, html, re.I) for pat in pats)
        )
        keys = []
        for pat, label in API_KEY_PATTERNS:
            for m in re.findall(pat, html, re.I)[:3]:
                keys.append({"label": label, "key": m})
        out["embedded_keys"] = keys
        # API hosts referenced in the HTML/JS
        hosts = sorted(set(re.findall(r'https?://([a-z0-9\.\-]+(?:api|bff|graphql|catalog)[a-z0-9\.\-]*)', html, re.I)) |
                       set(re.findall(r'https?://((?:api|bff|apis|catalog)[a-z0-9\.\-]+)', html, re.I)))
        out["api_hosts"] = hosts[:20]
        out["html_size"] = len(r.text)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def main():
    results = []
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30, http2=True) as client:
        for name, url in STORES.items():
            print(f"-- {name}", flush=True)
            results.append(probe(name, url, client))
    with open("recon/report.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    for r in results:
        print(json.dumps(r, ensure_ascii=False)[:400])


if __name__ == "__main__":
    sys.exit(main())
