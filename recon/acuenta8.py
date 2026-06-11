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

want_query = ["GetProductsByCategory", "GetCategoryTree", "GetProductsBySKU"]
want_frag = ["fragment ProductModel", "fragment CategoryModel", "fragment Product on",
             "fragment ProductCard", "fragment Price"]
seen_q=set(); seen_f=set()
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch)
    if not txt: continue
    for q in want_query:
        if q in seen_q: continue
        m = re.search(r'(query\s+'+q+r'\b.*?)`', txt, re.S)
        if m and len(m.group(1))<2500:
            print(f"\n===== QUERY {q} @{ch.split('/')[-1]} =====\n{m.group(1)[:2000]}")
            seen_q.add(q)
    for f in want_frag:
        if f in seen_f: continue
        m = re.search(r'('+re.escape(f)+r'\b.*?)`', txt, re.S)
        if m and len(m.group(1))<2000:
            print(f"\n----- {f} @{ch.split('/')[-1]} -----\n{m.group(1)[:1500]}")
            seen_f.add(f)
    # input shape for GetProductsByCategory
    for inp in ["GetProductsByCategoryInput", "getProductsByCategoryInput"]:
        m=re.search(re.escape(inp)+r'[^{]{0,40}\{[^}]{0,300}', txt)
        if m and inp not in seen_f:
            print(f"\n  INPUT {inp}: {m.group(0)[:280]}")
            seen_f.add(inp)
