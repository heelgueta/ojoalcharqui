import io, sys, re, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"

def H(key, origin="https://www.santaisabel.cl"):
    return {"User-Agent": UA, "Accept": "application/json, text/plain, */*",
            "Origin": origin, "Referer": origin + "/", "apikey": key}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True)

# 1) dig SI bundle for its own catalog apikey (raw grep, any webpack shape)
si = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                  headers={"User-Agent": UA, "Referer": "https://www.santaisabel.cl/"})
loader = si.get("https://assets.santaisabel.cl/2c5dc1d6173eb4c96226-bundle.js").text
# chunk filenames referenced from loader
chunk_ids = re.findall(r'"([0-9a-f]{16,})"', loader)
# try the generic chunk url pattern by scanning loader for any *.bundle.js refs
print("loader", len(loader))
keys=set()
# brute: fetch sibling chunks by guessing from any hashes + names in loader
names = re.findall(r'(\d+):"([a-z]+)"', loader)
hashes = dict(re.findall(r'(\d+):"([0-9a-f]{20})"', loader))
print("hashes found in loader:", len(hashes), "names:", names[:6])
base = "https://assets.santaisabel.cl/"
namemap = dict(names)
for cid, h in list(hashes.items()):
    u = base + f"{h}-{namemap.get(cid, cid)}.bundle.js"
    try: txt = si.get(u).text
    except Exception: continue
    if "{key:\"apiKey\"" in txt:
        for mm in re.finditer(r'(\w+):\{key:"apiKey",value:"([^"]+)"\}', txt):
            keys.add((mm.group(1), mm.group(2)))
si_keys = {k: v for k, v in keys}
print("SI catalog apikey:", si_keys.get("catalog"), "| search:", si_keys.get("search"))

# 2) test category tree with whichever keys we have + jumbo's, across sc
cand_keys = list({si_keys.get("catalog"), "WlVnnB7c1BblmgUPOfg"} - {None})
print("\n-- testing tree --")
for key in cand_keys:
    for sc in [3, 2, 4, 1, 6, 5]:
        try:
            r = c.get(f"{BASE}/catalog_system/pub/category/tree/3", params={"sc": sc}, headers=H(key))
            ct = r.headers.get("content-type","")
            if "json" in ct and r.status_code==200:
                j=r.json()
                if isinstance(j,list) and j:
                    print(f"OK key={key[:8]} sc={sc}: {len(j)} top cats, first={j[0].get('name')}")
                    continue
            print(f".. key={key[:8]} sc={sc}: {r.status_code} {r.text[:60]}")
        except Exception as e:
            print("ERR", e)
