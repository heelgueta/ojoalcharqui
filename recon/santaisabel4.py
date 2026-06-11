import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
si = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                  headers={"User-Agent": UA, "Referer": "https://www.santaisabel.cl/"})
loader = si.get("https://assets.santaisabel.cl/2c5dc1d6173eb4c96226-bundle.js").text
base = "https://assets.santaisabel.cl/"
chunks = re.findall(r'"([0-9a-f]{16,}-[a-z0-9]+\.bundle\.js)"', loader)
print("chunks:", len(chunks))
keys, bases = set(), set()
sc_chain = None
for ch in chunks:
    try: txt = si.get(base + ch).text
    except Exception: continue
    if "sm-web-api" in txt: bases.add("sm-web-api")
    for mm in re.finditer(r'(\w+):\{key:"apiKey",value:"([^"]+)"\}', txt):
        keys.add((mm.group(1), mm.group(2)))
    # store constant chain: re="...",X="...",Y="<sc>",Z="<scname>"
    for mm in re.finditer(r're="([a-z]+)",[A-Za-z]+="\1",[A-Za-z]+="(\d+)",[A-Za-z]+="([a-z0-9]+)"', txt):
        print("CONST:", mm.groups())
km = {k: v for k, v in keys}
print("catalog apikey:", km.get("catalog"), "| search:", km.get("search"))
print("has sm-web-api:", bases)
