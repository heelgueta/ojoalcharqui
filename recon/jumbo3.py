import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=90, verify=False, follow_redirects=True, headers=H)
html = c.get("https://www.jumbo.cl/").text

# 1) react-query state: queryKeys reveal endpoints; product shape
m = re.search(r'id="__REACT_QUERY_STATE__">(.*?)</script>', html, re.S)
if m:
    try:
        state = json.loads(m.group(1))
        qs = state.get("dehydratedState", {}).get("queries", [])
        print(f"{len(qs)} cached queries")
        for q in qs[:12]:
            print("  queryKey:", json.dumps(q.get("queryKey"), ensure_ascii=False)[:160])
        # first product shape
        for q in qs:
            data = q.get("state", {}).get("data", {})
            prods = data.get("products") if isinstance(data, dict) else None
            if prods:
                print("\nFIRST PRODUCT KEYS:", list(prods[0].keys()))
                print(json.dumps(prods[0], ensure_ascii=False)[:1400])
                break
    except Exception as e:
        print("state parse err", e)

# 2) other embedded config scripts (env, api base)
for sid in re.findall(r'<script[^>]*id="([^"]+)"', html):
    print("script id:", sid)

# 3) main app bundles on assets.jumbo.cl
appjs = re.findall(r'(https://assets\.jumbo\.cl/[^"]+\.js)', html)
print("\nassets.jumbo.cl js:", len(set(appjs)))
HOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:com|cl|net|io))(?=[/"\'` ])', re.I)
for b in list(set(appjs))[:8]:
    try: txt = c.get(b).text
    except Exception: continue
    api = sorted({h for h in HOST.findall(txt) if any(k in h for k in ["api","cencosud","smdigital","ecomm","graphql","gateway"])})
    if api:
        print(f"  {b.split('/')[-1]}:", api[:15])
