import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)
BASE = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(BASE + "cd0d88da729d1f572c46-bundle.js").text
hashmap = {}
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
for k,v in re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)): hashmap[k]=v
namemap={'3499':'cencosud','7032':'coupons'}
urls=[BASE+f"{h}-{namemap.get(cid,cid)}.bundle.js" for cid,h in hashmap.items()]

needles = ["products/search", "groceries-bff", "be-reg-groceries", "x-channel", "jumboclj", "salesChannel", "/products"]
for u in urls:
    try: txt = c.get(u).text
    except Exception: continue
    if "products/search" in txt or "groceries-bff" in txt:
        print(f"\n##### CHUNK {u.split('/')[-1]} #####")
        for nd in needles:
            for mm in list(re.finditer(re.escape(nd), txt))[:2]:
                i=mm.start()
                print(f"  [{nd}] ...{txt[max(0,i-180):i+180]}...".replace('\n',' '))
        break
