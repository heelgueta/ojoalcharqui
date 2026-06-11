import io, sys, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
     "Origin": "https://www.unimarc.cl", "Referer": "https://www.unimarc.cl/",
     "Content-Type": "application/json", "version": "1.0.0", "source": "web"}
c = httpx.Client(timeout=90, verify=False, headers=H)

def page(cat, fr, to):
    r = c.post(f"{BFF}/catalog/product/search",
               json={"categories": cat, "from": str(fr), "to": str(to), "salesChannel": "1"})
    if r.status_code != 200:
        return None, f"HTTP{r.status_code} {r.text[:80]}"
    ps = r.json().get("availableProducts", [])
    return ps, None

cat = "bebidas-y-licores/bebidas"
seen = set()
step = 50
fr = 0
for _ in range(40):
    ps, err = page(cat, fr, fr + step - 1)
    if err:
        print(f"from {fr}: {err}"); break
    ids = [p["item"]["itemId"] for p in ps]
    new = [i for i in ids if i not in seen]
    seen.update(ids)
    print(f"from {fr} to {fr+step-1}: got {len(ps)}, {len(new)} new, first={ps[0]['item']['name'][:30] if ps else None!r}")
    if len(ps) < step:
        break
    fr += step
print("TOTAL unique in category:", len(seen))
