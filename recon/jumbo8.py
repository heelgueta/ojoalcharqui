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

UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')
HEADERKEY = re.compile(r'(apikey|api[_-]?key|x-api-key|ocp-apim-subscription-key|consumer)', re.I)
hits = {}
for u in urls:
    try: txt = c.get(u).text
    except Exception: continue
    if "apikey" in txt.lower() or "api-key" in txt.lower():
        # find uuid values near an apikey assignment
        for m in re.finditer(r'(apikey|api[_-]?key|x-api-key)["\']?\s*[:=]\s*["\']?([0-9a-f]{8}-[0-9a-f-]{20,40}|[A-Za-z0-9]{20,40})', txt, re.I):
            hits.setdefault(u.split('/')[-1], set()).add((m.group(1), m.group(2)))
        # also context around 'No API key' style or header push with apikey
        for m in list(re.finditer(r'key:"apikey"[^}]{0,60}', txt, re.I))[:3]:
            hits.setdefault(u.split('/')[-1]+"#ctx", set()).add(m.group(0)[:90])
for k,v in hits.items():
    print(f"\n{k}:")
    for x in list(v)[:12]: print("   ", x)
