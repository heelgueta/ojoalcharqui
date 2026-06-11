import io, sys, re, httpx, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=3):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.5)
    return ""
home = get("https://www.acuenta.cl/")
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', home)))

# find GraphQL query/mutation definitions mentioning products/category
pat = re.compile(r'(query|mutation)\s+(\w+)\s*\(([^)]*)\)\s*\{', re.I)
hits = {}
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch)
    if not txt: continue
    for m in pat.finditer(txt):
        nm = m.group(2)
        if any(k in nm.lower() for k in ["product","categor","search","catalog","navigation","aisle","shelf"]):
            # capture the whole query body (balanced-ish: until matching count)
            start = m.start()
            body = txt[start:start+1200]
            hits.setdefault(nm, (ch.split('/')[-1], m.group(3), body))
for nm,(ch,args,body) in list(hits.items())[:8]:
    print(f"\n##### {nm}  @{ch}\n  args: {args}\n  {body[:700]}")
print("\nALL matching op names:", list(hits.keys()))
