import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
BFF = "https://bff-unimarc-ecommerce.unimarc.cl"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Origin": "https://www.unimarc.cl",
     "Referer": "https://www.unimarc.cl/", "Content-Type": "application/json", "version": "1.0.0", "source": "web"}
c = httpx.Client(timeout=60, verify=False, headers=H)

def names(r):
    if r.status_code != 200: return f"HTTP{r.status_code} {r.text[:90]}"
    ps = r.json().get("availableProducts", [])
    return (len(ps), [p["item"]["name"][:22] for p in ps[:2]], [p["item"]["name"][:22] for p in ps[-2:]])

# A) by-slug with slug in BODY
print("A) by-slug slug-in-body")
for body in [{"slug":"bebidas-y-licores/bebidas","page":0,"size":50,"salesChannel":"1"},
             {"categories":"bebidas-y-licores/bebidas","page":0,"size":50,"salesChannel":"1"}]:
    print(" ", body.get("slug") or body.get("categories"), names(c.post(f"{BFF}/catalog/product/search/by-slug/", json=body)))

# B) from/to subsetting on arroz (22 items)
print("B) from/to on arroz (22 total)")
arroz = "despensa/arroz-y-legumbres/arroz"
for fr,to in [(0,9),(10,19),(0,21),(0,49)]:
    print(f"  from{fr} to{to}:", names(c.post(f"{BFF}/catalog/product/search", json={"categories":arroz,"from":fr,"to":to,"salesChannel":"1"})))

# C) page on arroz with from/to combined
print("C) page+size variations on arroz")
for body in [{"categories":arroz,"page":1,"size":10,"salesChannel":"1"},
             {"categories":arroz,"page":0,"size":10,"salesChannel":"1"}]:
    print("  ", body, names(c.post(f"{BFF}/catalog/product/search", json=body)))

# D) Next.js chunk manifest search for the real call
print("D) searching _next chunks")
html = c.get("https://www.unimarc.cl/", headers={"User-Agent":"Mozilla/5.0"}).text
chunks = set(re.findall(r'/_next/static/[^"\']+\.js', html))
# also buildManifest
bm = re.findall(r'/_next/static/[^"\']+_buildManifest\.js', html)
found=False
for ch in list(chunks)[:40]:
    try: js = c.get("https://www.unimarc.cl"+ch).text
    except: continue
    if "product/search" in js or "categories" in js and "salesChannel" in js:
        for needle in ["product/search","salesChannel","by-slug"]:
            i = js.find(needle)
            if i>=0:
                print(f"  [{ch.split('/')[-1]}] ...{js[max(0,i-200):i+200]}...")
                found=True
        break
if not found: print("  (no chunk matched)")
