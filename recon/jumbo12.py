import io, sys, json, httpx
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
def H(key):
    return {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*", "Accept-Language": "es-CL,es;q=0.9",
            "Origin": "https://www.jumbo.cl", "Referer": "https://www.jumbo.cl/", "apikey": key}
c = httpx.Client(timeout=40, verify=False, follow_redirects=True)

bases = {
    "bff": "https://bff.jumbo.cl/catalog",
    "smweb_v1": "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1",
    "smweb_v3": "https://sm-web-api.ecomm.cencosud.com/catalog/api/v3",
    "smcore": "https://sm-api-core.ecomm.cencosud.com/catalog",
}
keys = {"catalog": "WlVnnB7c1BblmgUPOfg", "search": "tqqk4wy5Y7twMTFcZvQh"}
paths = ["/products/search/?ft=leche&page=1&sc=1"]

for bn, base in bases.items():
    for kn, key in keys.items():
        for p in paths:
            try:
                r = c.get(base + p, headers=H(key))
                msg = ""
                if "json" in r.headers.get("content-type",""):
                    j = r.json()
                    msg = json.dumps(j, ensure_ascii=False)[:200]
                else:
                    msg = r.text[:90]
                flag = "  <<<<< OK" if r.status_code == 200 else ""
                print(f"{r.status_code} [{bn}/{kn}] {p}\n     {msg}{flag}\n")
            except Exception as e:
                print(f"ERR [{bn}/{kn}]: {e}")
