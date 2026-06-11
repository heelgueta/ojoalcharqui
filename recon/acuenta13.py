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
    except: return {"_txt":r.text[:300]}
Q = """query($i: GetProductsByCategoryInput!){
  getProductsByCategory(getProductsByCategoryInput:$i){
    pagination{ page pages }
    category{ reference name products{ sku ean name brand price previousPrice pricePerSubUnit unit subUnit subQty photosUrl stock isAvailable } }
  }
}"""
for pag in [{"page":1,"perPage":5},{"page":1,"maxResults":5},{"page":1,"limit":5,"offset":0},
            {"page":1},{"currentPage":1,"pageSize":5},{"from":0,"size":5}]:
    inp={"categoryReference":"5501","storeReference":"580","clientId":"SUPER_BODEGA","pagination":pag}
    r=gql(Q,{"i":inp})
    if "errors" in r: print(f"{pag} -> {r['errors'][0]['message'][:200]}")
    else:
        d=r["data"]["getProductsByCategory"]; ps=d["category"]["products"]
        print(f"\nOK pag={pag} -> pagination={d['pagination']} n={len(ps)}")
        for p in ps[:3]: print("   ", json.dumps(p,ensure_ascii=False)[:280])
        break
