import io, sys, re, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)
BASE = "https://assets-jumbo.ecomm.cencosud.com/"
loader = c.get(BASE + "cd0d88da729d1f572c46-bundle.js").text
hm = re.search(r'\{((?:\d+:"[0-9a-f]+",?){5,})\}', loader)
hashmap = dict(re.findall(r'(\d+):"([0-9a-f]+)"', hm.group(1)))
txt = c.get(BASE + f"{hashmap['8434']}-8434.bundle.js").text

# extract the apiKey service map: catalog:{key:"apiKey",value:"..."}
print("== service apiKey map ==")
for svc in ["catalog","products","abandonedCart","search","bff","cms"]:
    for m in re.finditer(rf'{svc}\s*:\s*\{{key:"apiKey",value:"([^"]+)"\}}', txt):
        print(f"   {svc}: {m.group(1)}")
# generic: name:{key:"apiKey",value:"X"}
print("\n== all {key:apiKey,value} entries ==")
for m in re.finditer(r'(\w+):\{key:"apiKey",value:"([^"]+)"\}', txt):
    print(f"   {m.group(1)} = {m.group(2)}")

# trace Oe base for products/search
i = txt.find("/products/search/${Ht}")
print("\n== products/search context ==")
print(txt[max(0,i-600):i+120].replace("\n"," "))
