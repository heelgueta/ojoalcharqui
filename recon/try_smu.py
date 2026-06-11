"""Try the SMU (Unimarc/Alvi) BFF product endpoints directly."""
import json
import httpx

H = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-CL,es;q=0.9",
    "Origin": "https://www.unimarc.cl",
    "Referer": "https://www.unimarc.cl/",
    "Content-Type": "application/json",
}

BFFS = ["https://bff-unimarc-ecommerce.unimarc.cl", "https://bff-unimarc-web.unimarc.cl/bff-api"]


def show(tag, r):
    print(f"\n### {tag} -> {r.status_code} ({len(r.content)} bytes)")
    ct = r.headers.get("content-type", "")
    if "json" in ct:
        try:
            j = r.json()
            print(json.dumps(j, ensure_ascii=False)[:1500])
            return j
        except Exception as e:
            print("json parse fail", e)
    print(r.text[:600])
    return None


def main():
    slug = "bebidas-y-licores/bebidas"
    with httpx.Client(headers=H, timeout=40, verify=False, follow_redirects=True) as c:
        for bff in BFFS:
            # GET style with query params
            for path, params in [
                (f"/catalog/product/search/by-slug/{slug}", {"page": 0, "size": 5}),
                (f"/catalog/product/search/by-slug/{slug}", {"page": "0", "perPage": "5", "salesChannel": "1"}),
            ]:
                try:
                    r = c.get(bff + path, params=params)
                    show(f"GET {bff}{path} {params}", r)
                except Exception as e:
                    print("ERR", bff, path, e)
            # POST style
            for path, body in [
                ("/catalog/product/search/by-slug/" + slug, {"page": 0, "size": 5, "salesChannel": "1"}),
                ("/catalog/product/facets", {"slug": slug, "page": 0, "size": 5}),
            ]:
                try:
                    r = c.post(bff + path, json=body)
                    show(f"POST {bff}{path} {body}", r)
                except Exception as e:
                    print("ERR", bff, path, e)


if __name__ == "__main__":
    main()
