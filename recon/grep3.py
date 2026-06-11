import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
c = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                 headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.unimarc.cl/"})
html = c.get("https://www.unimarc.cl/").text
app = [x for x in sorted(set(re.findall(r'/_next/static/[^"\']+\.js', html))) if "_app-" in x][0]
js = c.get("https://www.unimarc.cl" + app).text

for fn in ["productsSearch()", "postFacets()"]:
    i = js.find(fn)
    print(f"\n===== {fn} @ {i} =====")
    if i >= 0:
        print(js[i-120:i+650])

# Find callers of productsSearch to see what body they build (params: categories/page/etc.)
for m in re.finditer(r'productsSearch', js):
    seg = js[m.start():m.start()+1]
# search for where the body with categories+page is assembled near 'salesChannel'
for kw in ["salesChannel", "perPage", "pageNumber", "\"page\"", "categories:"]:
    idxs = [mm.start() for mm in re.finditer(re.escape(kw), js)][:3]
    for i in idxs:
        print(f"\n--- {kw} @ {i} ---")
        print(js[i-160:i+120])
