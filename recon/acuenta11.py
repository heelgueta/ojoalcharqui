import io, sys, re, httpx, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=3):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.5)
    return ""
home = get("https://www.acuenta.cl/")
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', home)))
targets = ["CatalogProductModel","ProductPriceModel","on Promotion","PromotionModel","ProductFields"]
seen=set()
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch)
    if not txt: continue
    for t in targets:
        if t in seen: continue
        m = re.search(r'(fragment\s+\w+\s+on\s+'+re.escape(t.replace("on ",""))+r'\s*\{.*?)`', txt, re.S)
        if not m:
            m = re.search(r'(fragment\s+'+re.escape(t)+r'\s+on\s+\w+\s*\{.*?)`', txt, re.S)
        if m and len(m.group(1))<1800:
            print(f"\n===== {t} @{ch.split('/')[-1]} =====\n{m.group(1)[:1500]}")
            seen.add(t)
print("\nfound:", seen)
