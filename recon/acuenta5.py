import io, sys, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
KEY = "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e"
def H(extra=None):
    h={"User-Agent":"Mozilla/5.0","Accept":"application/json","Content-Type":"application/json",
       "Origin":"https://www.acuenta.cl","Referer":"https://www.acuenta.cl/"}
    if extra: h.update(extra)
    return h
c=httpx.Client(timeout=30, verify=False, follow_redirects=True)

endpoints = [
    "https://superbodega.instaleap.io/api/v3","https://super-bodega.instaleap.io/api/v3",
    "https://superbodegaacuenta.instaleap.io/api/v3","https://acuenta.instaleap.io/api/v3",
    "https://nextgentheadless.instaleap.io/api/v3","https://nextgentheadless.instaleap.io/api/v2",
    "https://walmart-chile.instaleap.io/api/v3","https://walmartchile.instaleap.io/api/v3",
]
hdrs = [{"Apikey":KEY},{"X-Api-Key":KEY},{"apikey":KEY},{"Authorization":KEY}]
body = {"query":"{ __typename }"}
for ep in endpoints:
    ok=False
    for hd in hdrs:
        try:
            r=c.post(ep, headers=H(hd), json=body)
            if r.status_code in (200,400,401,422):
                print(f"{r.status_code} {ep} [{list(hd)[0]}] :: {r.text[:120]}")
                ok=True
                if r.status_code==200: break
        except Exception as e:
            pass
    if not ok:
        # try GET host root
        try:
            r=c.get(ep.replace("/api/v3","").replace("/api/v2",""), headers=H())
            print(f"GET {r.status_code} {ep}")
        except Exception as e:
            print(f"DNSFAIL {ep}")
