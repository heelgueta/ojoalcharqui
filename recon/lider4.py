import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "text/html,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try:
            r = httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url)
            return r
        except Exception:
            time.sleep(0.6)
    return None

def walk_find(obj, want_keys, path="", out=None, depth=0):
    if out is None: out=[]
    if depth>8: return out
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k in want_keys:
                out.append((path+"/"+k, type(v).__name__, json.dumps(v,ensure_ascii=False)[:120]))
            walk_find(v, want_keys, path+"/"+k, out, depth+1)
    elif isinstance(obj, list) and obj:
        walk_find(obj[0], want_keys, path+"[0]", out, depth+1)
    return out

for url in ["https://super.lider.cl/search?q=leche",
            "https://super.lider.cl/aplecategory/Despensa",
            "https://super.lider.cl/catalogo"]:
    r = get(url)
    if not r: print("FAIL", url); continue
    print(f"\n==== {url} -> {r.status_code} {r.url} ({len(r.text)}b)")
    m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
    if not m:
        print("  no NEXT_DATA"); continue
    try: nd = json.loads(m.group(1))
    except Exception as e: print("  parse err", e); continue
    s = json.dumps(nd, ensure_ascii=False)
    print("  NEXT_DATA", len(s), "bytes")
    # look for product arrays
    for hit in walk_find(nd, {"products","items","itemsV2","records","searchResult","price","usItemId","name"})[:18]:
        print("   ", hit)
