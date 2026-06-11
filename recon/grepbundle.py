import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.unimarc.cl/"}
c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H)
html = c.get("https://www.unimarc.cl/").text
scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
scripts = [("https://www.unimarc.cl" + s if s.startswith("/") else s) for s in scripts]
needle = "product/search"
for s in scripts:
    if any(d in s for d in ["gtm", "facebook", "hotjar"]):
        continue
    try:
        js = c.get(s).text
    except Exception:
        continue
    if needle in js:
        for m in re.finditer(re.escape(needle), js):
            a, b = max(0, m.start() - 400), min(len(js), m.end() + 400)
            print(f"\n=== {s.split('/')[-1]} @ {m.start()} ===")
            print(js[a:b])
        break
