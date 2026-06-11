import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://www.unimarc.cl",
     "Referer": "https://www.unimarc.cl/", "Content-Type": "application/json", "version": "1.0.0", "source": "web"}
c = httpx.Client(timeout=60, verify=False, headers=H)
cat = "bebidas-y-licores/bebidas"

def firstid(body):
    r = c.post(f"{BFF}/catalog/product/search", json=body)
    if r.status_code != 200:
        return f"HTTP{r.status_code}: {r.text[:80]}"
    ps = r.json().get("availableProducts", [])
    return (len(ps), ps[0]["item"]["name"][:30] if ps else None, ps[-1]["item"]["name"][:30] if ps else None)

base = {"categories": cat, "size": 50, "salesChannel": "1"}
print("baseline page0:", firstid({**base, "page": 0}))
# Try many pagination conventions, compare to baseline
for variant in [
    {"from": 50, "to": 99}, {"offset": 50}, {"start": 50}, {"skip": 50},
    {"page": 2}, {"page": 2, "perPage": 50}, {"pageNumber": 2}, {"currentPage": 2},
    {"page": 1, "size": 50}, {"from": 50, "to": 100, "size": 50},
]:
    b = {**base, **variant}
    print(variant, "->", firstid(b))
# Try bigger size
for sz in [50, 100, 250, 500]:
    print(f"size={sz} ->", firstid({"categories": cat, "size": sz, "salesChannel": "1", "page": 0}))
