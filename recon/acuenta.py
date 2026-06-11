import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url)
        except Exception: time.sleep(0.6)
    return None

r = get("https://www.acuenta.cl/")
html = r.text if r else ""
print("home", len(html), "->", r.url if r else None)

# instaleap api hosts + keys
HOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:instaleap\.io|acuenta\.cl|lider\.cl|walmartchile\.cl|cloudfront\.net))(?=[/"\'`])', re.I)
hosts={}
for h in HOST.findall(html):
    hosts[h]=hosts.get(h,0)+1
print("hosts:", dict(sorted(hosts.items(), key=lambda x:-x[1])[:15]))

# chunks
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', html)))
chunks += re.findall(r'src="(https?://[^"]+\.js)"', html)
print("chunks", len(chunks))
needles = ["instaleap","apiKey","x-api-key","Authorization","graphql","getProducts","searchProducts",
           "storeId","clientId","X-Client","tenant","SUPER_BODEGA","/catalog","getNavigationMenu","products"]
found={}
for ch in [html] + [("https://www.acuenta.cl"+c if c.startswith("/") else c) for c in chunks[:25]]:
    txt = ch if ch.startswith("<") else ""
    if not txt:
        rr=get(ch); txt=rr.text if rr else ""
    for nd in needles:
        i=txt.find(nd)
        if i>=0 and nd not in found:
            found[nd]=txt[max(0,i-90):i+120].replace("\n"," ")
for nd in needles:
    if nd in found: print(f"\n[{nd}] {found[nd]}")
