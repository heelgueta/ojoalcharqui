import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
c = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                 headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.unimarc.cl/"})
html = c.get("https://www.unimarc.cl/").text
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', html)))
app = [x for x in chunks if "_app-" in x][0]
js = c.get("https://www.unimarc.cl" + app).text

# context around getSearchesBySlugV2
for fn in ["getSearchesBySlugV2", "by-slug/", "version:r", "x-api-version", '"version"']:
    i = js.find(fn)
    print(f"\n=== {fn} @ {i} ===")
    if i >= 0:
        print(js[max(0, i-300):i+350])

# find what r / version resolves to: look for `version:` assignments and app version constants
for m in re.finditer(r'version:\s*([a-zA-Z0-9_."]+)', js):
    seg = js[max(0,m.start()-60):m.start()+40]
    if "source" in seg or "web" in seg or "bff" in seg.lower():
        print("\nVER-CTX:", seg)
# version-looking string constants
print("\nSEMVER consts:", sorted(set(re.findall(r'"(\d+\.\d+\.\d+)"', js)))[:20])
