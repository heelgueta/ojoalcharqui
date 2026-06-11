import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
def H(): return {"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json",
                 "Origin":"https://www.acuenta.cl","Referer":"https://www.acuenta.cl/","Apikey":KEY}
c=httpx.Client(timeout=30, verify=False, follow_redirects=True)

for ep in ["https://nextgentheadless.instaleap.io/api/v3","https://acuenta.instaleap.io/api/v3"]:
    print(f"\n===== {ep} =====")
    # list query fields
    q={"query":"{ __schema { queryType { fields { name args { name } } } } }"}
    try:
        r=c.post(ep, headers=H(), json=q)
        j=r.json()
        flds=j.get("data",{}).get("__schema",{}).get("queryType",{}).get("fields",[])
        if flds:
            for f in flds:
                if any(k in f["name"].lower() for k in ["product","categor","search","catalog","navigation","menu","store"]):
                    print("  ", f["name"], "(", ",".join(a["name"] for a in f["args"]), ")")
        else:
            print("  introspection blocked:", json.dumps(j)[:160])
    except Exception as e:
        print("  ERR", e)
