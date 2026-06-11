import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EP = "https://nextgentheadless.instaleap.io/api/v3"
KEY = "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
HD = {"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json",
      "Origin":"https://www.acuenta.cl","Referer":"https://www.acuenta.cl/","Apikey":KEY}
c=httpx.Client(timeout=30, verify=False)
def gql(q,v):
    r=c.post(EP, headers=HD, json={"query":q,"variables":v})
    try: return r.json()
    except: return {"_txt":r.text[:300]}

Q = """query($i: GetProductsByCategoryInput!){
  getProductsByCategory(getProductsByCategoryInput:$i){
    pagination{ page pages }
    category{ reference name
      products{ sku ean name brand price previousPrice pricePerSubUnit promotionPricePerSubUnit
                unit subUnit subQty photosUrl stock isAvailable
                promotion{ type description } } }
  }
}"""
# get a real leaf category from the tree first
tree = gql("query($i: GetCategoryInput!){ getCategory(getCategoryInput:$i){ reference name subCategories{ reference name subCategories{ reference name } } } }",
           {"i":{"clientId":"SUPER_BODEGA","storeReference":"580"}})
cats = tree.get("data",{}).get("getCategory",[])
print("top categories:", [(x["reference"], x["name"]) for x in cats][:10])
# pick a leaf
def first_leaf(nodes):
    for n in nodes:
        subs=n.get("subCategories") or []
        if subs:
            r=first_leaf(subs)
            if r: return r
        else:
            return n
    return None
leaf = first_leaf(cats) or cats[0]
print("leaf:", leaf["reference"], leaf["name"])

for inp in [
  {"categoryReference":leaf["reference"],"storeReference":"580","clientId":"SUPER_BODEGA","pagination":{"page":1,"perPage":5}},
  {"categoryReference":leaf["reference"],"storeReference":"580","clientId":"SUPER_BODEGA","pagination":{"page":1,"size":5}},
]:
    r=gql(Q,{"i":inp})
    if "errors" in r: print("ERR:", r["errors"][0]["message"][:140])
    else:
        d=r["data"]["getProductsByCategory"]
        ps=d["category"]["products"]
        print(f"\nOK pag={d['pagination']} n={len(ps)}")
        for p in ps[:3]: print("  ", json.dumps(p, ensure_ascii=False)[:300])
        break
