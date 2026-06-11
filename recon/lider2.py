import io, sys, re, httpx, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}

def newc(): return httpx.Client(timeout=40, verify=False, follow_redirects=True, headers=H)

def get(url, tries=3):
    for _ in range(tries):
        try:
            return newc().get(url).text
        except Exception:
            continue
    return ""

html = get("https://super.lider.cl/")
print("home bytes", len(html))

# __NEXT_DATA__
m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
if m:
    try:
        nd = json.loads(m.group(1))
        # walk for api hosts / config
        s = json.dumps(nd, ensure_ascii=False)
        print("NEXT_DATA bytes", len(s))
        for kw in ["pegasus","walmart","apiKey","api_key","x-api-key","graphql",
                   "consumerId","CONSUMER","ORCHESTRA","baseUrl","BASE_URL","endpoint"]:
            i = s.lower().find(kw.lower())
            if i>=0: print(f"  [{kw}] ...{s[max(0,i-80):i+100]}...")
        rc = nd.get("runtimeConfig") or nd.get("props",{}).get("pageProps",{})
        print("\nruntimeConfig keys:", list((nd.get("runtimeConfig") or {}).keys())[:30])
    except Exception as e:
        print("nd parse err", e)

# hosts anywhere in html
HOST = re.compile(r'https://([a-z0-9\-\.]+\.(?:com|cl|net|io))(?=[/"\'`])', re.I)
hosts={}
for h in HOST.findall(html):
    if any(k in h for k in ["walmart","lider","pegasus","api","graphql","orchestra","gateway"]):
        hosts[h]=hosts.get(h,0)+1
print("\nHTML api hosts:"); [print(f"  {n:4} {h}") for h,n in sorted(hosts.items(),key=lambda x:-x[1])[:25]]
