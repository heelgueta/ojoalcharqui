"""SMU BFF with required version/source headers."""
import io
import json
import sys

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "https://bff-unimarc-ecommerce.unimarc.cl"


def H(extra=None):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CL,es;q=0.9",
        "Origin": "https://www.unimarc.cl",
        "Referer": "https://www.unimarc.cl/",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def show(tag, r):
    print(f"\n### {tag} -> {r.status_code} ({len(r.content)} bytes)")
    try:
        j = r.json()
        print(json.dumps(j, ensure_ascii=False)[:2500])
        return j
    except Exception:
        print(r.text[:600])
        return None


def main():
    slug = "bebidas-y-licores/bebidas"
    hdr_variants = [
        {"version": "web", "source": "web"},
        {"version": "1.0.0", "source": "web"},
        {"version": "1.0.0", "source": "ecommerce"},
    ]
    with httpx.Client(timeout=40, verify=False, follow_redirects=True) as c:
        for hv in hdr_variants:
            r = c.post(f"{BASE}/catalog/product/facets", headers=H(hv),
                       json={"slug": slug, "page": 0, "size": 5})
            show(f"facets hdr={hv}", r)

        # once we know working headers, try product search variants
        hv = {"version": "1.0.0", "source": "web"}
        for path, body in [
            (f"/catalog/product/search/by-slug/{slug}", {"page": 0, "size": 5, "salesChannel": "1"}),
            (f"/catalog/product/search/by-slug/{slug}", {"page": 0, "size": 5}),
            ("/catalog/product/search", {"slug": slug, "page": 0, "size": 5, "salesChannel": "1"}),
        ]:
            r = c.post(BASE + path, headers=H(hv), json=body)
            show(f"POST {path} {body}", r)
        for path, params in [
            (f"/catalog/product/search/by-slug/{slug}", {"page": 0, "size": 5, "salesChannel": 1}),
        ]:
            r = c.get(BASE + path, headers=H(hv), params=params)
            show(f"GET {path} {params}", r)


if __name__ == "__main__":
    main()
