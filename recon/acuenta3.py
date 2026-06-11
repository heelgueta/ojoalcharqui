import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url)
        except Exception: time.sleep(0.6)
    return None

home = get("https://www.acuenta.cl/").text
# category URLs /ca/...
cats = sorted(set(re.findall(r'"(?:path|href|url)":"(/ca/[a-z0-9][a-z0-9/_\-]+)"', home)))
print(f"{len(cats)} /ca/ links. sample:", cats[:8])

# does a category page SSR products? look for product-ish keys
if cats:
    cu = "https://www.acuenta.cl" + cats[0]
    r = get(cu)
    h = r.text if r else ""
    print(f"\ncategory {cats[0]} -> {len(h)}b")
    for kw in ['"sku"','"price"','"name"','productId','"stock"','"slug"','searchProducts','"products"','grossPrice','"ean"']:
        i=h.find(kw)
        if i>=0: print(f"  [{kw}] ...{h[max(0,i-50):i+90]}...".replace("\n"," "))

# find the instaleap GraphQL endpoint + apikey usage in chunks
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', home)))
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch)
    txt = txt.text if txt else ""
    if "instaleap.io/api" in txt and ("Apikey" in txt or "apiKey" in txt or "api-key" in txt.lower()):
        for kw in ["instaleap.io/api","Apikey","X-Api-Key","headers:"]:
            i=txt.find(kw)
            if i>=0: print(f"\n[{ch.split('/')[-1]} :: {kw}] ...{txt[max(0,i-80):i+140]}...".replace("\n"," "))
        # GraphQL product query
        for q in re.findall(r'(query\s+\w*[Pp]roduct\w*[^`]{0,400})', txt)[:1]:
            print("  QUERY:", q[:300])
        break
