import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EP = "https://nextgentheadless.instaleap.io/api/v3"
KEY = "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
HD = {"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json",
      "Origin":"https://www.acuenta.cl","Referer":"https://www.acuenta.cl/","Apikey":KEY}
c=httpx.Client(timeout=30, verify=False)
def gql(q,v):
    r=c.post(EP, headers=HD, json={"query":q,"variables":v});
    try: return r.json()
    except: return r.text[:300]

# progressively richer product selection; read errors to learn fields
sel_variants = [
  "sku name price brand",
  "sku name price brand photoUrl photosUrl ean stock unit",
  "sku name price formattedPrice brand photosUrl ean stock isAvailable promotion{ description }",
  "id sku name price priceBeforeTaxes brand photosUrl unit clickMultiplier maxQty isAvailable nutritionalInfo ean promotion{ type description conditions } subUnit",
]
for sel in sel_variants:
    q=f"""query($i: GetProductsByCategoryInput!){{
      getProductsByCategory(getProductsByCategoryInput:$i){{
        pagination{{ page pages }}
        category{{ reference name products{{ {sel} }} }}
      }}
    }}"""
    inp={"categoryReference":"55","storeReference":"580","clientId":"SUPER_BODEGA","pagination":{"page":1,"perPage":5}}
    r=gql(q,{"i":inp})
    if "errors" in r:
        print("SEL:", sel[:40], "-> ERR:", r["errors"][0]["message"][:160])
    else:
        cat=r["data"]["getProductsByCategory"]
        prods=cat["category"].get("products",[])
        print(f"\nOK sel='{sel[:50]}...' pagination={cat['pagination']} nprods={len(prods)}")
        if prods: print("  first:", json.dumps(prods[0], ensure_ascii=False)[:500])
        break
