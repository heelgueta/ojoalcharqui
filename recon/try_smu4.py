"""Nail SMU category enumeration + real pagination."""
import io
import json
import sys

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"


def H():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.unimarc.cl",
        "Referer": "https://www.unimarc.cl/",
        "Content-Type": "application/json",
        "version": "1.0.0",
        "source": "web",
    }


def main():
    c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H())

    tree = c.get(f"{BFF}/catalog/categories").json()
    # print shape of one real (non-Ofertas) category
    real = [x for x in tree if x.get("id", 0) < 900000]
    print("TOP CATEGORIES:", [(x["id"], x["name"]) for x in tree][:20])
    sample = real[0]
    print("\nSAMPLE NODE keys:", list(sample.keys()))
    print(json.dumps(sample, ensure_ascii=False)[:900])

    # Try search by category id and by slug, check pagination differs
    def first3(j):
        ps = j.get("availableProducts", [])
        return [p["item"]["name"][:40] for p in ps[:3]], len(ps)

    slug = "despensa/arroz-y-legumbres/arroz"
    print("\n-- by-slug route variants")
    for method, path in [("GET", f"/catalog/product/search/by-slug/{slug}"),
                         ("POST", f"/catalog/product/search/by-slug/{slug}")]:
        for body in [{"page": 0, "size": 50, "salesChannel": "1"}]:
            r = c.request(method, BFF + path, json=(body if method == "POST" else None),
                          params=(body if method == "GET" else None))
            print(method, path, "->", r.status_code, r.text[:120] if r.status_code != 200 else first3(r.json()))

    print("\n-- /catalog/product/search with category filters, pagination check")
    for body in [
        {"slug": slug, "category": slug, "page": 0, "size": 50, "salesChannel": "1"},
        {"category": slug, "page": 0, "size": 50, "salesChannel": "1"},
        {"categories": slug, "page": 0, "size": 50, "salesChannel": "1"},
        {"slug": slug, "page": 0, "size": 50, "salesChannel": "1", "sort": ""},
    ]:
        r = c.post(f"{BFF}/catalog/product/search", json=body)
        if r.status_code == 200:
            print(body, "->", first3(r.json()))

    print("\n-- pagination on a working body")
    for pg in [0, 1, 2]:
        body = {"slug": "arroz", "category": slug, "page": pg, "size": 10, "salesChannel": "1"}
        r = c.post(f"{BFF}/catalog/product/search", json=body)
        if r.status_code == 200:
            print("page", pg, first3(r.json()))


if __name__ == "__main__":
    main()
