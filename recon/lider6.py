import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "text/html,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.6)
    return ""

def extract_products(html):
    """Find balanced JSON objects that contain a usItemId, parse the ones that look like products."""
    out, n = [], len(html)
    for mm in re.finditer(r'"usItemId":"(\d+)"', html):
        # walk backwards to the opening brace of this object
        i = mm.start()
        depth, start = 0, None
        j = i
        while j >= 0:
            ch = html[j]
            if ch == '}': depth += 1
            elif ch == '{':
                if depth == 0: start = j; break
                depth -= 1
            j -= 1
        if start is None: continue
        # walk forwards to matching close
        depth, k = 0, start
        while k < n:
            ch = html[k]
            if ch == '{': depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: break
            k += 1
        blob = html[start:k+1]
        try:
            obj = json.loads(blob)
            if "name" in obj and ("priceInfo" in obj or "price" in obj):
                out.append(obj)
        except Exception:
            continue
    return out

html = get("https://super.lider.cl/search?q=leche")
prods = extract_products(html)
print(f"search leche: extracted {len(prods)} products")
if prods:
    p = prods[0]
    print("KEYS:", [k for k in p.keys()][:40])
    pi = p.get("priceInfo", {})
    print("sample:", p.get("usItemId"), p.get("name"), "| brand", p.get("brand"),
          "| price", p.get("price"), "| pi", {k:pi.get(k) for k in ["itemPrice","linePrice","wasPrice","unitPrice","savings"]})
    print("img:", (p.get("imageInfo") or {}).get("thumbnailUrl"))
    print("cat:", (p.get("category") or {}).get("categoryPathId"), (p.get("category") or {}).get("categoryPath") if p.get("category") else None)

# pagination
for pg in [1,2,3]:
    h = get(f"https://super.lider.cl/search?q=leche&page={pg}")
    pr = extract_products(h)
    ids = {x.get("usItemId") for x in pr}
    print(f"page {pg}: {len(pr)} products, first={pr[0]['name'][:30] if pr else None}")
