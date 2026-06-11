import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)
BASE = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(BASE + "cd0d88da729d1f572c46-bundle.js").text

# chunk js filename builder: u(e)= hashmap[e] + "-" + (namemap[e]||e) + ".bundle.js"
# extract both maps
hashmap = {}
m = re.search(r'\.u=function\(e\)\{return"?\+?\{([^}]+)\}\[e\]', loader) or \
    re.search(r'return\s*"?\+?\{([0-9:"a-f,]+)\}\[e\]\+"-"', loader)
namemap = {}
nm = re.search(r'\(\{([0-9:"a-z,]+)\}\[e\]\|\|e\)\+"\.bundle\.js"', loader)
if nm:
    for k,v in re.findall(r'(\d+):"([a-z]+)"', nm.group(1)):
        namemap[k]=v
# hashes: big map of id:"hash"
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
if hm:
    for k,v in re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)):
        hashmap[k]=v
print("chunks found:", len(hashmap), "named:", namemap)

# build urls
urls = []
for cid,h in hashmap.items():
    name = namemap.get(cid, cid)
    urls.append(BASE + f"{h}-{name}.bundle.js")
print("sample urls:", urls[:3])

HOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:com|cl|br|net|io))(?=[/"\'`])', re.I)
PATH = re.compile(r'["\'`](/(?:api|catalog|products?|search|v\d|graphql|bff|categories?)[a-z0-9/_\-{}:.]{2,70})["\'`]', re.I)
allhosts, allpaths = {}, set()
for u in urls:
    try: txt = c.get(u).text
    except Exception: continue
    for h in HOST.findall(txt):
        if any(k in h for k in ["cencosud","smdigital","ecomm","api","gateway","graphql","cloudfront"]) and "assets" not in h:
            allhosts[h]=allhosts.get(h,0)+1
    allpaths |= set(PATH.findall(txt))
print("\nAPI HOSTS:")
for h,n in sorted(allhosts.items(), key=lambda x:-x[1]): print(f"  {n:4} {h}")
print("\nPATHS (product/search/category):")
for p in sorted(allpaths):
    if any(k in p.lower() for k in ["product","search","categ","catalog"]): print("  ", p)
