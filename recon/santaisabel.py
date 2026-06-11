"""Recon Santa Isabel (Cencosud). Find catalog apikey + sc, test sm-web-api base."""
import io, sys, re, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
c = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                 headers={"User-Agent": UA, "Referer": "https://www.santaisabel.cl/"})

html = c.get("https://www.santaisabel.cl/").text
print("html", len(html))
# find the loader bundle (assets-santaisabel...)
bn = set(re.findall(r'(https://assets[^"]*?/[A-Za-z0-9]+-bundle\.js)', html))
print("bundles:", bn)
# also __REACT_QUERY_STATE__ for sc + product shape
m = re.search(r'id="__REACT_QUERY_STATE__">(.*?)</script>', html, re.S)
if m:
    state = m.group(1)
    sc = set(re.findall(r'"(sai?cl[a-z0-9]+)"', state))
    print("sc-ish tokens:", sc)

# load loader + chunks, grep apikeys + sm-web-api base
loader_url = next(iter(bn), None)
keys = set()
if loader_url:
    base = loader_url.rsplit("/", 1)[0] + "/"
    loader = c.get(loader_url).text
    hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
    hashmap = dict(re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1))) if hm else {}
    nm = re.search(r'\(\{([0-9:"a-z,]+)\}\[e\]\|\|e\)\+"\.bundle\.js"', loader)
    namemap = dict(re.findall(r'(\d+):"([a-z]+)"', nm.group(1))) if nm else {}
    print("chunks", len(hashmap), "named", namemap)
    found_base = set()
    for cid, h in hashmap.items():
        u = base + f"{h}-{namemap.get(cid, cid)}.bundle.js"
        try: txt = c.get(u).text
        except Exception: continue
        if "sm-web-api" in txt:
            found_base.add("sm-web-api.ecomm.cencosud.com")
        for mm in re.finditer(r'(\w+):\{key:"apiKey",value:"([^"]+)"\}', txt):
            keys.add((mm.group(1), mm.group(2)))
        # constants like re="saisabelcl" sc etc
        for mm in re.finditer(r'\bre="([a-z]+)",[A-Z]="\1",[A-Z]="(\d+)",[A-Z]="([a-z0-9]+)"', txt):
            print("CONST chain:", mm.groups())
    print("bases:", found_base)
    print("apikeys (catalog/search):")
    for k, v in sorted(keys):
        if k in ("catalog", "search", "products"):
            print("  ", k, v)
