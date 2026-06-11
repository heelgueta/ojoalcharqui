import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H)

def probe(url, **kw):
    try:
        r = c.get(url, **kw)
        ct = r.headers.get("content-type","")
        body = ""
        if "json" in ct:
            try: body = json.dumps(r.json(), ensure_ascii=False)[:300]
            except: body = r.text[:200]
        else:
            body = r.text[:160]
        print(f"{r.status_code} {url}\n     {body}\n")
    except Exception as e:
        print(f"ERR {url}: {e}\n")

print("=== VTEX legacy catalog ===")
probe("https://www.jumbo.cl/api/catalog_system/pub/products/search?_from=0&_to=2")
probe("https://www.jumbo.cl/api/catalog_system/pub/category/tree/3")

print("=== VTEX intelligent search ===")
probe("https://www.jumbo.cl/api/io/_v/api/intelligent-search/product_search/?query=leche&page=1&count=2")
probe("https://www.jumbo.cl/api/io/_v/api/intelligent-search/product_search/category-1/frutas-y-verduras?page=1&count=2")
probe("https://www.jumbo.cl/_v/segment/graphql/v1")
probe("https://www.jumbo.cl/api/io/_v/public/searchgraphql/v1")

print("=== loader bundle: find chunks + api base ===")
loader = c.get("https://assets-jumbo.ecomm.cencosud.com/cd0d88da729d1f572c46-bundle.js").text
print("loader size", len(loader))
# webpack chunk map / publicPath
for kw in ["publicPath", ".js", "ecomm", "api", "https://"]:
    hits = [m.start() for m in re.finditer(re.escape(kw), loader)][:2]
    for i in hits:
        print(f"  [{kw}] {loader[max(0,i-60):i+80]!r}")
hosts = sorted(set(re.findall(r'https://([a-z0-9\-\.]+\.(?:com|cl|br|net))', loader)))
print("  loader hosts:", hosts)
