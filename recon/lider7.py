import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "text/html,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try:
            r=httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url); return r
        except Exception: time.sleep(0.6)
    return None

home = get("https://super.lider.cl/").text
# internal link patterns
links = sorted(set(re.findall(r'"(?:url|canonicalUrl|href)":"(/[a-z0-9][a-z0-9/_\-]+)"', home)))
buckets={}
for l in links:
    seg=l.split("/")[1]
    buckets.setdefault(seg,[]).append(l)
print("link prefixes:", {k:len(v) for k,v in sorted(buckets.items())})
for seg in ["browse","category","cp","catalog","aisle","departamentos","shop","c"]:
    if seg in buckets: print(f"  {seg}:", buckets[seg][:5])

# also look for taxonomy / departments in flight data
for kw in ['"browse"','"seoBrowseRelmUrl"','categoryPath','"departments"','"aisle"','/cp/','/browse/']:
    i=home.find(kw)
    if i>=0: print(f"\n[{kw}] ...{home[max(0,i-60):i+140]}...".replace("\n"," "))
