import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Referer": "https://www.acuenta.cl/"}
def get(url, tries=4, hdr=None):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=hdr or H).get(url)
        except Exception: time.sleep(0.6)
    return None
home = get("https://www.acuenta.cl/").text

for kw in ["apiBaseUrl","apiKey","storeId","storeReference","clientId","X-Api-Key",
           "instaleap.io","70196ab63cc","graphqlUrl","baseUrl","api/v3","api/v2"]:
    for m in list(re.finditer(re.escape(kw), home))[:2]:
        i=m.start(); print(f"[{kw}] ...{home[max(0,i-70):i+110]}...".replace("\n"," "))

# any non-demo instaleap host in home
hosts = sorted(set(re.findall(r'https://([a-z0-9\-]+\.instaleap\.io)', home)))
print("\ninstaleap hosts in home:", hosts)
# the 60-hex key present in home?
print("60-hex key in home:", "70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e" in home)
