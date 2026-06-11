import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "text/html,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.6)
    return ""

html = get("https://super.lider.cl/search?q=leche")
print("bytes", len(html))
for kw in ["usItemId","canonicalUrl","priceInfo","currentPrice","__APOLLO_STATE__","swag/graphql",
           "operationName","sha256Hash","persistedQuery","x-apollo","WM_CONSUMER","wm_consumer",
           "\"price\"","linePrice","itemsV2","\"name\"","departmentName","catalogProduct"]:
    i = html.find(kw)
    if i>=0:
        print(f"\n[{kw}] @{i}\n   ...{html[max(0,i-90):i+160]}...".replace("\n"," "))

# RSC flight product object: find a JSON object with usItemId
m = re.search(r'\{[^{}]*usItemId[^{}]*\}', html)
if m: print("\nRSC product-ish:", m.group(0)[:400])
# any graphql endpoint references
for h in sorted(set(re.findall(r'(/swag/graphql[^"\'\\ ]*)', html)))[:5]: print("gql path:", h)
for h in sorted(set(re.findall(r'(https://[a-z0-9\.\-]+/[a-z0-9/_\-]*graphql[a-z0-9/_\-]*)', html)))[:5]: print("gql url:", h)
