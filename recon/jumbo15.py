import io, sys, json, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Origin": "https://www.jumbo.cl",
     "Referer": "https://www.jumbo.cl/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

def probe(url):
    try:
        r = c.get(url)
        ct = r.headers.get("content-type","")
        if "json" in ct:
            j = r.json()
            if isinstance(j, list):
                print(f"{r.status_code} {url}\n   LIST n={len(j)} first={j[0].get('productName') if j else None}")
            elif isinstance(j, dict):
                prods = j.get("products")
                if prods is not None:
                    print(f"{r.status_code} {url}\n   OBJ products={len(prods)} recordsFiltered={j.get('recordsFiltered')}")
                else:
                    print(f"{r.status_code} {url}\n   OBJ keys={list(j.keys())} {json.dumps(j,ensure_ascii=False)[:150]}")
        else:
            print(f"{r.status_code} {url}\n   {r.text[:100]}")
    except Exception as e:
        print("ERR", url, e)

# category browse format attempts (cat 27 = Despensa)
for u in [
    f"{BASE}/products/search/despensa?page=1&sc=1",
    f"{BASE}/products/search/Despensa?page=1&sc=1",
    f"{BASE}/products/search/?fq=C:/27/&page=1&sc=1",
    f"{BASE}/products/search/?map=c&fq=C:27&page=1&sc=1",
    f"{BASE}/products/search/?category=27&page=1&sc=1",
    f"{BASE}/products/search/27?page=1&sc=1",
    f"{BASE}/products/search/?O=OrderByScoreDESC&page=1&sc=1&fq=C:/27/",
    f"{BASE}/products/categorytree/3?sc=1",
    f"{BASE}/categorytree/3?sc=1",
    f"{BASE}/products/search/?page=1&sc=1",
]:
    probe(u)
