import io, sys, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Origin": "https://www.jumbo.cl",
     "Referer": "https://www.jumbo.cl/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

def n(url):
    try:
        r = c.get(url); j = r.json()
        return len(j) if isinstance(j, list) else f"obj {list(j.keys())}"
    except Exception as e: return f"ERR {e}"

# page size params
for extra in ["", "&resultsPerPage=50", "&count=50", "&_from=0&_to=49", "&pageSize=50",
              "&rows=50", "&ps=50", "&perPage=50", "&limit=50"]:
    print(f"fq=C:/27/ page=1{extra}: n={n(f'{BASE}/products/search/?fq=C:/27/&page=1&sc=1{extra}')}")

# does fq=C:/27/ (top) include subtree? compare count of leaf vs top by paging a few
print("\n-- browse pagination check on a leaf (cat 3 = Leches) --")
seen=set()
for pg in range(1,8):
    j=c.get(f"{BASE}/products/search/?fq=C:/1/3/&page={pg}&sc=1").json()
    ids=[p['productId'] for p in j] if isinstance(j,list) else []
    new=[i for i in ids if i not in seen]; seen.update(ids)
    print(f"  page {pg}: {len(ids)} items, {len(new)} new, first={j[0]['productName'][:30] if ids else None}")
    if len(ids)<12: break
print("  total unique:", len(seen))
