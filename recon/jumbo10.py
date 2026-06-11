import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)
BASE = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(BASE + "cd0d88da729d1f572c46-bundle.js").text
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
hashmap = dict(re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)))
namemap={'3499':'cencosud','7032':'coupons'}
urls=[BASE+f"{h}-{namemap.get(cid,cid)}.bundle.js" for cid,h in hashmap.items()]

# Find the config object that maps api bases + apikeys (the env chunk)
for u in urls:
    try: txt = c.get(u).text
    except Exception: continue
    if "bff.jumbo.cl/catalog" in txt:
        i = txt.find("bff.jumbo.cl/catalog")
        print(f"### {u.split('/')[-1]} : bff_catalog context")
        print(txt[max(0,i-200):i+1200].replace("\n"," "))
        # apikey assignments in this chunk
        print("\n-- apikeys in chunk --")
        for m in re.finditer(r'(apikey|apiKey)["\']?\s*[:,]\s*["\']?([A-Za-z0-9\-]{16,40})', txt):
            print("   ", m.group(1), m.group(2))
        # header interceptor: where apikey header is pushed
        for m in list(re.finditer(r'apikey', txt, re.I))[:8]:
            j=m.start(); print("   ctx:", txt[max(0,j-70):j+70].replace("\n"," "))
        break
