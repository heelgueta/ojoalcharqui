import io, sys, re, httpx, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=3):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.5)
    return ""
home = get("https://www.acuenta.cl/")
chunks = sorted(set(re.findall(r'/_next/static/[^"\']+\.js', home)))
# find object literal passed as getProductsByCategoryInput
for ch in chunks:
    txt = get("https://www.acuenta.cl"+ch)
    if "getProductsByCategoryInput" not in txt: continue
    for m in re.finditer(r'getProductsByCategoryInput', txt):
        seg = txt[m.start():m.start()+260]
        if "{" in seg and ("categoryReference" in seg or "maxResults" in seg or "page" in seg.lower()):
            print(ch.split('/')[-1], "::", seg.replace("\n"," ")[:240], "\n")
    # also the input type fields if present
    mm = re.search(r'input GetProductsByCategoryInput\s*\{[^}]{0,400}', txt)
    if mm: print("INPUT DEF:", mm.group(0)[:400])
    break

# EP probe with likely top-level fields
EP="https://nextgentheadless.instaleap.io/api/v3"; KEY="70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
HD={"User-Agent":"Mozilla/5.0","Content-Type":"application/json","Origin":"https://www.acuenta.cl","Apikey":KEY}
c=httpx.Client(timeout=30, verify=False)
Q="""query($i: GetProductsByCategoryInput!){ getProductsByCategory(getProductsByCategoryInput:$i){ pagination{ page pages } category{ products{ sku ean name brand price previousPrice pricePerSubUnit subUnit subQty stock isAvailable } } } }"""
for extra in [{"page":1,"maxResults":5},{"page":1,"productsPerPage":5},{"currentPage":1,"maxResults":5},
              {"page":1},{"page":1,"perPageCount":5}]:
    inp={"categoryReference":"5501","storeReference":"580","clientId":"SUPER_BODEGA",**extra}
    r=c.post(EP, headers=HD, json={"query":Q,"variables":{"i":inp}}).json()
    if "errors" in r: print(extra, "->", r["errors"][0]["message"][:120])
    else:
        d=r["data"]["getProductsByCategory"]; ps=d["category"]["products"]
        print(f"\nOK {extra} pag={d['pagination']} n={len(ps)}")
        for p in ps[:3]: print("  ", json.dumps(p,ensure_ascii=False)[:260])
        break
