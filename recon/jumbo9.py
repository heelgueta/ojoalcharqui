import io, sys, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Accept-Language": "es-CL,es;q=0.9",
     "Origin": "https://www.jumbo.cl", "Referer": "https://www.jumbo.cl/",
     "apikey": "dd19ac7b075be07d758a28b2"}
c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H)
BFF = "https://bff.jumbo.cl/catalog"

def probe(url, **kw):
    try:
        r = c.get(url, **kw)
        if "json" in r.headers.get("content-type",""):
            j=r.json(); s=json.dumps(j,ensure_ascii=False)
            print(f"{r.status_code} {url}\n   {'keys='+str(list(j.keys())) if isinstance(j,dict) else 'list len '+str(len(j))} | {len(s)}b\n   {s[:500]}\n")
            return j
        print(f"{r.status_code} {url}\n   {r.text[:160]}\n")
    except Exception as e:
        print(f"ERR {url}: {e}\n")

for u in [
    f"{BFF}/products/search/leche?page=1&sc=1",
    f"{BFF}/products/search/?page=1&sc=1",
    f"{BFF}/categories?sc=1",
    f"{BFF}/categories/tree?sc=1",
    f"{BFF}/category/tree/3?sc=1",
    f"{BFF}/products/search/category-1/lacteos-y-bebidas?page=1&sc=1",
]:
    probe(u)
