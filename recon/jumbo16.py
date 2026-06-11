import io, sys, json, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Origin": "https://www.jumbo.cl",
     "Referer": "https://www.jumbo.cl/", "apikey": "WlVnnB7c1BblmgUPOfg"}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

def probe(url, hdr=None):
    try:
        r = c.get(url, headers=hdr)
        ct = r.headers.get("content-type","")
        body = json.dumps(r.json(), ensure_ascii=False)[:240] if "json" in ct else r.text[:110]
        print(f"{r.status_code} {url}\n   {body}\n")
    except Exception as e:
        print("ERR", url, e)

print("== VTEX category tree via BFF ==")
for base in ["https://sm-web-api.ecomm.cencosud.com/catalog/api/v1",
             "https://bff.jumbo.cl/catalog"]:
    for depth in [50, 3]:
        probe(f"{base}/catalog_system/pub/category/tree/{depth}?sc=1")
    probe(f"{base}/products/facets/?fq=C:/27/&sc=1")
    probe(f"{base}/facets/?map=c&query=/27&sc=1")

# CMS menu endpoint from bundle
assets = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(assets + "cd0d88da729d1f572c46-bundle.js", headers={"User-Agent": H["User-Agent"]}).text
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
hashmap = dict(re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)))
txt = c.get(assets + f"{hashmap['8434']}-8434.bundle.js", headers={"User-Agent": H["User-Agent"]}).text
print("== getMenu / cms api base ==")
for nd in ["getMenu","acf","cms/","/menu","new-cms","cl-ccom-cms"]:
    for m in list(re.finditer(re.escape(nd), txt))[:2]:
        i=m.start(); print(f"  [{nd}] ...{txt[max(0,i-110):i+110]}...".replace('\n',' '))
