import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)

html = c.get("https://www.jumbo.cl/").text
bundle = "https://assets-jumbo.ecomm.cencosud.com/cd0d88da729d1f572c46-bundle.js"
# find actual bundle name(s) in html
bnames = re.findall(r'(https://assets-jumbo\.ecomm\.cencosud\.com/[A-Za-z0-9]+-bundle\.js)', html)
print("bundle names in html:", set(bnames))
texts = {"html": html}
for b in set(bnames) or {bundle}:
    try: texts[b.split("/")[-1]] = c.get(b).text
    except Exception as e: print("fetch fail", b, e)

ALLHOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:com|cl|net|io))(?=[/"\'` ])', re.I)
for tag, txt in texts.items():
    hosts = {}
    for h in ALLHOST.findall(txt):
        if any(k in h for k in ["cencosud","smdigital","algolia","constructor","ecomm","cloudfront","jumbo","api"]):
            hosts[h] = hosts.get(h,0)+1
    print(f"\n== {tag} ({len(txt)} bytes) interesting hosts:")
    for h,n in sorted(hosts.items(), key=lambda x:-x[1])[:30]:
        print(f"   {n:5}  {h}")

# search html for embedded api config / graphql / apiKey
for needle in ["graphql", "apiKey", "x-api-key", "api_key", "/api/", "ecomm.cencosud", "search?", "products"]:
    i = texts["html"].find(needle)
    if i>=0:
        print(f"\n[html:{needle}] ...{texts['html'][max(0,i-120):i+160]}...")
