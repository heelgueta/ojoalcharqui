"""Confirm SMU pagination, full-catalog enumeration, and Alvi parity."""
import io
import json
import sys

import httpx

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def H(origin):
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-CL,es;q=0.9",
        "Origin": origin,
        "Referer": origin + "/",
        "Content-Type": "application/json",
        "version": "1.0.0",
        "source": "web",
    }


def keys_summary(j):
    if not isinstance(j, dict):
        return type(j).__name__
    prods = j.get("availableProducts") or j.get("products") or []
    return {
        "top_keys": list(j.keys()),
        "n_products": len(prods),
        "resource": j.get("resource"),
        "first_name": (prods[0]["item"]["name"] if prods else None),
    }


def main():
    with httpx.Client(timeout=60, verify=False, follow_redirects=True) as c:
        # 1) Category tree endpoints (try a few)
        for path in ["/catalog/categories", "/catalog/category/tree", "/catalog/menu",
                     "/catalog/categories/tree", "/category/tree"]:
            try:
                r = c.get("https://bff-unimarc-ecommerce.unimarc.cl" + path, headers=H("https://www.unimarc.cl"))
                print(f"GET {path} -> {r.status_code} ({len(r.content)}b) {r.text[:200]}")
            except Exception as e:
                print("ERR", path, e)

        # 2) Pagination: big size + page 2; empty slug = all?
        base = "https://bff-unimarc-ecommerce.unimarc.cl/catalog/product/search"
        for body in [
            {"slug": "despensa", "page": 0, "size": 100, "salesChannel": "1"},
            {"slug": "despensa", "page": 1, "size": 100, "salesChannel": "1"},
            {"slug": "", "page": 0, "size": 50, "salesChannel": "1"},
            {"category": "", "page": 0, "size": 50, "salesChannel": "1"},
        ]:
            try:
                r = c.post(base, headers=H("https://www.unimarc.cl"), json=body)
                print(f"\nPOST search {body} -> {r.status_code}")
                if r.status_code == 200:
                    print(keys_summary(r.json()))
                else:
                    print(r.text[:200])
            except Exception as e:
                print("ERR", body, e)

        # 3) Alvi parity
        for bff in ["https://bff-alvi-web.alvi.cl", "https://bff-alvi-ecommerce.alvi.cl"]:
            try:
                r = c.post(bff + "/catalog/product/search", headers=H("https://www.alvi.cl"),
                           json={"slug": "despensa", "page": 0, "size": 5, "salesChannel": "1"})
                print(f"\nALVI {bff} -> {r.status_code}")
                if r.status_code == 200:
                    print(keys_summary(r.json()))
                else:
                    print(r.text[:200])
            except Exception as e:
                print("ERR alvi", bff, e)


if __name__ == "__main__":
    main()
