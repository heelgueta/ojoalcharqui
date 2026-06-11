import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try:
            return httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception:
            time.sleep(0.5)
    return ""

html = get("https://super.lider.cl/")
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', html)))
print("chunks:", len(chunks))

needles = ["pegasus","/orchestra","graphql","product_search","/products","api-proxy","x-api-key",
           "consumerId","WM_CONSUMER","developer.api.us.walmart","/search","productByDepartment","getProducts"]
found = {}
for ch in chunks:
    txt = get("https://super.lider.cl" + ch, tries=2)
    if not txt: continue
    for nd in needles:
        for m in list(re.finditer(re.escape(nd), txt))[:1]:
            i=m.start()
            found.setdefault(nd, []).append((ch.split('/')[-1], txt[max(0,i-110):i+130].replace("\n"," ")))
# print first hit per needle
for nd in needles:
    if nd in found:
        ch, ctx = found[nd][0]
        print(f"\n[{nd}] @{ch}\n   {ctx}")
