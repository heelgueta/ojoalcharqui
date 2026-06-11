import io, sys, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Accept-Language": "es-CL,es;q=0.9",
     "Origin": "https://www.jumbo.cl", "Referer": "https://www.jumbo.cl/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

print("== FULL PRODUCT SHAPE ==")
r = c.get(f"{BASE}/products/search/?ft=leche&page=1&sc=1")
j = r.json()
print("type", type(j).__name__, "len", len(j) if hasattr(j,'__len__') else '?')
p = j[0] if isinstance(j, list) else j
print("keys:", list(p.keys()))
print(json.dumps(p, ensure_ascii=False)[:1800])

print("\n== pagination: page 2 first product ==")
r2 = c.get(f"{BASE}/products/search/?ft=leche&page=2&sc=1")
j2 = r2.json()
print("page1[0]:", j[0].get("productName"), "| page2[0]:", (j2[0].get("productName") if j2 else None), "| n1", len(j), "n2", len(j2))

print("\n== category tree probes ==")
for path in ["/categories?sc=1", "/categories/tree?sc=1", "/category/tree?sc=1",
             "/categories/3?sc=1", "/menu?sc=1", "/category-tree?sc=1", "/tree?sc=1",
             "/categories/menu?sc=1", "/products/categorytree/3?sc=1"]:
    try:
        rr = c.get(BASE + path)
        body = rr.text[:120]
        if "json" in rr.headers.get("content-type",""):
            body = json.dumps(rr.json(), ensure_ascii=False)[:200]
        print(f"{rr.status_code} {path} :: {body}")
    except Exception as e:
        print("ERR", path, e)
