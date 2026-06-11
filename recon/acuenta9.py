import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EP = "https://nextgentheadless.instaleap.io/api/v3"
KEY = "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
HD = {"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json",
      "Origin":"https://www.acuenta.cl","Referer":"https://www.acuenta.cl/","Apikey":KEY}
c=httpx.Client(timeout=30, verify=False)
def gql(q, v):
    try:
        r=c.post(EP, headers=HD, json={"query":q,"variables":v})
        return r.json()
    except Exception as e: return {"_err":str(e)}

print("== GetCategoryTree ==")
for inp in [{"clientId":"SUPER_BODEGA","storeReference":"580"},
            {"clientId":"SUPER_BODEGA","storeReference":"580","categoryReference":""}]:
    q="query($i: GetCategoryInput!){ getCategory(getCategoryInput:$i){ reference name } }"
    r=gql(q, {"i":inp})
    print(inp, "->", json.dumps(r, ensure_ascii=False)[:300])

print("\n== GetProductsByCategory (probe fields) ==")
# need a category reference; first try a broad selection of product fields
q = """query($i: GetProductsByCategoryInput!){
  getProductsByCategory(getProductsByCategoryInput:$i){
    pagination{ page pages total }
    category{ reference name products{ sku name price brand } }
  }
}"""
for inp in [
  {"categoryReference":"01","storeReference":"580","clientId":"SUPER_BODEGA","pagination":{"page":1,"perPage":10}},
  {"categoryReference":"01","storeReference":"580","clientId":"SUPER_BODEGA","pagination":{"page":1,"limit":10}},
]:
    r=gql(q, {"i":inp})
    print(json.dumps(inp), "->", json.dumps(r, ensure_ascii=False)[:400])
