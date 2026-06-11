import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://www.lider.cl/"}
c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H)

for start in ["https://www.lider.cl/supermercado", "https://www.lider.cl/", "https://super.lider.cl/"]:
    try:
        r = c.get(start)
        print(f"{r.status_code} {start} -> {r.url} ({len(r.text)}b)")
    except Exception as e:
        print("ERR", start, e)

html = c.get("https://www.lider.cl/supermercado").text
# next data + chunks
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', html)))
print("chunks:", len(chunks))
HOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:com|cl|net|io))(?=[/"\'`])', re.I)
PATH = re.compile(r'["\'`](/(?:api|graphql|pegasus|orchestra|service|product|search|catalog|v\d)[a-z0-9/_\-{}]{2,70})["\'`]', re.I)
hosts, paths, keys = {}, set(), set()
for ch in [html] + ["https://www.lider.cl"+x for x in chunks[:25]]:
    txt = ch if ch.startswith("<") else (c.get(ch).text if ch.startswith("http") else "")
    for h in HOST.findall(txt):
        if any(k in h for k in ["walmart","lider","pegasus","api","graphql","gateway","orchestra"]):
            hosts[h]=hosts.get(h,0)+1
    paths |= set(PATH.findall(txt))
    for m in re.finditer(r'(x-api-key|apikey|api_key|consumer-id|WM_|x-wm|client[_-]?id)["\']?\s*[:=]\s*["\']([^"\']{6,60})', txt, re.I):
        keys.add((m.group(1), m.group(2)))
print("\nHOSTS:"); [print(f"  {n:4} {h}") for h,n in sorted(hosts.items(),key=lambda x:-x[1])[:25]]
print("\nPATHS:"); [print("  ", p) for p in sorted(paths)[:40]]
print("\nKEYS:"); [print("  ", k) for k in sorted(keys)[:25]]
