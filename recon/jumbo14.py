import io, sys, json, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Origin": "https://www.jumbo.cl",
     "Referer": "https://www.jumbo.cl/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

j = c.get(f"{BASE}/products/search/?ft=leche&page=1&sc=1").json()
p = j[0]
print("== items[0] (price/ean/images) ==")
print(json.dumps(p["items"][0], ensure_ascii=False, indent=1)[:1600])

# hunt category tree endpoint in bundle 8434
assets = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(assets + "cd0d88da729d1f572c46-bundle.js", headers={"User-Agent": H["User-Agent"]}).text
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
hashmap = dict(re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)))
txt = c.get(assets + f"{hashmap['8434']}-8434.bundle.js", headers={"User-Agent": H["User-Agent"]}).text
print("\n== category/menu endpoint references in bundle ==")
for nd in ["categorytree","categoryTree","/menu","departments","navigation","category-tree","categories/","getMenu","menu/"]:
    for m in list(re.finditer(re.escape(nd), txt))[:2]:
        i=m.start(); print(f"  [{nd}] ...{txt[max(0,i-90):i+90]}...".replace('\n',' '))
