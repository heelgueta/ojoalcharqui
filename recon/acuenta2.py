import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.6)
    return ""
home = get("https://www.acuenta.cl/")
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', home)))
print("chunks", len(chunks))

API = re.compile(r'https://([a-z0-9\-\.]+\.instaleap\.io)(?=[/"\'`])', re.I)
APIANY = re.compile(r'https://([a-z0-9\-\.]+\.(?:instaleap\.io|cloud\.instaleap\.io|amazonaws\.com))(?=[/"\'`])', re.I)
hosts={}; ops=set(); keys=set(); gqlpaths=set()
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch, tries=2)
    if not txt: continue
    for h in APIANY.findall(txt):
        if "wanda" not in h and "files" not in h: hosts[h]=hosts.get(h,0)+1
    ops |= set(re.findall(r'operationName:"([A-Za-z]+)"', txt))
    ops |= set(re.findall(r'"operationName":"([A-Za-z]+)"', txt))
    for m in re.finditer(r'(apiKey|Apikey|x-api-key|X-Api-Key|authorization)["\']?\s*[:=]\s*["\']([^"\']{8,60})', txt):
        keys.add((m.group(1), m.group(2)))
    gqlpaths |= set(re.findall(r'(https://[a-z0-9\.\-]+/[a-z0-9/_\-]*graphql[a-z0-9/_\-]*)', txt))
    gqlpaths |= set(re.findall(r'(https://[a-z0-9\.\-]+\.instaleap\.io/[a-z0-9/_\-]+)', txt))
print("\nINSTALEAP/API hosts:", dict(sorted(hosts.items(), key=lambda x:-x[1])[:15]))
print("\nGQL/api urls:"); [print("  ", u) for u in sorted(gqlpaths)[:20]]
print("\nkeys:"); [print("  ", k) for k in sorted(keys)[:15]]
print("\noperationNames (product-ish):", sorted([o for o in ops if any(k in o.lower() for k in ['product','categor','search','catalog','menu','store'])])[:30])
print("all ops sample:", sorted(ops)[:30])
