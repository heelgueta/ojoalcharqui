import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
     "Origin": "https://www.unimarc.cl", "Referer": "https://www.unimarc.cl/",
     "version": "1.0.0", "source": "web", "channel": "UNIMARC"}
c = httpx.Client(timeout=90, verify=False, headers=H)

def summarize(r):
    if r.status_code != 200:
        return f"HTTP{r.status_code} {r.text[:120]}"
    j = r.json()
    if isinstance(j, dict):
        ap = j.get("availableProducts", [])
        na = j.get("notAvailableProducts", [])
        return {"keys": list(j.keys()), "available": len(ap), "notAvailable": len(na),
                "first": ap[0]["item"]["name"][:35] if ap else None}
    return f"type={type(j).__name__} len={len(j) if hasattr(j,'__len__') else '?'}"

for slug in ["despensa/arroz-y-legumbres/arroz", "bebidas-y-licores/bebidas", "bebidas-y-licores", "despensa"]:
    # clean GET, no query params
    r = c.get(f"{BFF}/catalog/product/search/by-slug/{slug}")
    print(f"by-slug GET /{slug}\n   ->", summarize(r))
