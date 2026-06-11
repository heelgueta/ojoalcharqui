import io, sys, re, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"
si = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                  headers={"User-Agent": UA, "Referer": "https://www.santaisabel.cl/"})
loader = si.get("https://assets.santaisabel.cl/2c5dc1d6173eb4c96226-bundle.js").text

# Show the chunk-url-building region
for kw in ["bundle.js", ".u=", "miniCssF", "jsonpScriptSrc", "publicPath", "p="]:
    i = loader.find(kw)
    if i >= 0:
        print(f"[{kw}] {loader[max(0,i-80):i+160]!r}\n")

# Any big id:hash maps anywhere
maps = re.findall(r'\{(?:\s*\d+:"[0-9a-f]{6,}",?){4,}\}', loader)
print("hash-map blocks:", len(maps))
for m in maps[:2]:
    print(m[:300])
