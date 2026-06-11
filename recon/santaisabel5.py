import io, sys, re, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
def H(origin):
    return {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
            "Origin": origin, "Referer": origin+"/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True)

# grep SI bundle for store/sc constants
si = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                  headers={"User-Agent": UA, "Referer": "https://www.santaisabel.cl/"})
loader = si.get("https://assets.santaisabel.cl/2c5dc1d6173eb4c96226-bundle.js").text
chunks = re.findall(r'"([0-9a-f]{16,}-[a-z0-9]+\.bundle\.js)"', loader)
base="https://assets.santaisabel.cl/"
for ch in chunks:
    try: txt=si.get(base+ch).text
    except: continue
    for kw in ['clj','saisabel','isabelcl']:
        for mm in list(re.finditer(rf'"[a-z0-9]*{kw}[a-z0-9]*"', txt))[:3]:
            i=mm.start(); print(f"[{ch[:8]} {kw}] {txt[max(0,i-60):i+40]}".replace('\n',' '))

# empirical: same category, vary sc + origin, compare product set & price
print("\n-- product set by sc (cat 3 Leches) --")
for sc in [1,2,3,4,5,6,7,8,11]:
    try:
        j=c.get(f"{BASE}/products/search/", params={"fq":"C:/1/3/","page":1,"sc":sc},
                headers=H("https://www.santaisabel.cl")).json()
        if isinstance(j,list) and j:
            it=j[0]; pr=it['items'][0]['sellers'][0]['commertialOffer']['Price']
            seller=it['items'][0]['sellers'][0].get('sellerName')
            print(f"  sc={sc}: {it['productName'][:34]:34} ${pr} seller={seller}")
        else:
            print(f"  sc={sc}: empty/obj")
    except Exception as e:
        print(f"  sc={sc}: ERR {e}")
