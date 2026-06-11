"""Recon pass 3: find working catalog endpoints per store."""
import json
import re
import sys

import httpx

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
H = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9"}

out = {}


def show(label, r, body_chars=500):
    try:
        j = r.json()
        txt = json.dumps(j, ensure_ascii=False)
    except Exception:
        txt = r.text
    out[label] = {"status": r.status_code, "body": txt[:body_chars], "len": len(txt)}
    print(f"== {label}: {r.status_code} len={len(txt)}")
    print(txt[:body_chars].replace("\n", " "))
    print()


def main():
    c = httpx.Client(headers=H, follow_redirects=True, timeout=40, verify=False)

    # --- JUMBO: mine the main bundle for API hosts/keys ---
    try:
        js = c.get("https://assets-jumbo.ecomm.cencosud.com/cd0d88da729d1f572c46-bundle.js").text
        hosts = sorted(set(re.findall(r'https?://[a-z0-9\.\-]+[a-z0-9\.\-/]*api[a-z0-9\.\-/]*', js, re.I)))
        xkeys = re.findall(r'x-api-key["\']?\s*[:=]\s*["\']([^"\']{10,})["\']', js, re.I)
        apikeys = re.findall(r'(?:apiKey|api_key)["\']?\s*[:=]\s*["\']([A-Za-z0-9\-_\.]{16,})["\']', js)
        # also look for any quoted url-ish strings with cencosud/smdigital
        cenco = sorted(set(re.findall(r'["\'](https?://[^"\']*(?:cencosud|smdigital)[^"\']*)["\']', js, re.I)))
        out["jumbo:bundle"] = {"api_hosts": hosts[:30], "x_api_keys": xkeys[:5], "apikeys": apikeys[:10], "cenco_urls": cenco[:30]}
        print("== jumbo bundle:", json.dumps(out["jumbo:bundle"], indent=1)[:2000])
    except Exception as e:
        print("jumbo bundle err", e)

    # --- UNIMARC: BFF + Next.js data routes ---
    try:
        html = c.get("https://www.unimarc.cl/").text
        m = re.search(r'"buildId