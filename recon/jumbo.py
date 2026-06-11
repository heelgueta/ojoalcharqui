"""Recon Jumbo (Cencosud / SMdigital). Find the product API host + shape."""
import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://www.jumbo.cl/"}
c = httpx.Client(timeout=60, verify=False, follow_redirects=True, headers=H)

html = c.get("https://www.jumbo.cl/").text
print("html size", len(html))

# bundles
bundles = re.findall(r'src="(https://assets-jumbo[^"]+\.js[^"]*)"', html)
bundles += [b for b in re.findall(r'src="(/[^"]+\.js[^"]*)"', html)]
bundles = ["https://www.jumbo.cl"+b if b.startswith("/") else b for b in bundles]
print("bundles:", len(bundles))

HOSTS = re.compile(r'https://([a-z0-9\-]+\.(?:smdigital\.cl|cencosud\.com|cencosud\.cl|cencosudx\.com|ecomm\.cencosud\.com|algolia\.net|algolianet\.com|constructor\.io|cloudfront\.net))', re.I)
PATHS = re.compile(r'["\'`](/(?:api|catalog|product|search|v\d|graphql|bff)[a-z0-9/_\-{}]{2,70})["\'`]', re.I)
KEYS  = re.compile(r'["\']?(x-api-key|apiKey|api_key|appId|applicationId|x-algolia-[a-z\-]+|client[_-]?id|token)["\']?\s*[:=]\s*["\']([A-Za-z0-9\-_\.]{8,80})["\']', re.I)

hosts, paths, keys = set(), set(), set()
for src in [html] + bundles[:20]:
    txt = src if src.startswith("<") or src.startswith("{") else ""
    if not txt:
        try: txt = c.get(src).text
        except Exception: continue
    hosts |= set(m.lower() for m in HOSTS.findall(txt))
    paths |= set(PATHS.findall(txt))
    keys  |= set(KEYS.findall(txt))

print("\nHOSTS:"); [print("  ", h) for h in sorted(hosts)]
print("\nPATHS:"); [print("  ", p) for p in sorted(paths)[:60]]
print("\nKEYS:"); [print("  ", k) for k in sorted(keys)[:30]]
