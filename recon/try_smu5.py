import io, sys, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://www.unimarc.cl",
     "Referer": "https://www.unimarc.cl/", "Content-Type": "application/json", "version": "1.0.0", "source": "web"}
c = httpx.Client(timeout=60, verify=False, headers=H)
cat = "bebidas-y-licores/bebidas"
seen = set()
for pg in range(0, 12):
    r = c.post(f"{BFF}/catalog/product/search", json={"categories": cat, "page": pg, "size": 50, "salesChannel": "1"})
    j = r.json()
    ps = j.get("availableProducts", [])
    ids = [p["item"]["itemId"] for p in ps]
    new = [i for i in ids if i not in seen]
    seen.update(ids)
    print(f"page {pg}: {len(ps)} products, {len(new)} new, first={ps[0]['item']['name'][:35] if ps else None!r}")
    if not ps:
        break
print("TOTAL unique:", len(seen))
