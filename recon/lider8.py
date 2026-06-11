import io, sys, re, httpx, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
     "Accept": "text/html,*/*", "Accept-Language": "es-CL,es;q=0.9", "Referer": "https://super.lider.cl/"}
def get(url, tries=4):
    for _ in range(tries):
        try: return httpx.Client(timeout=45, verify=False, follow_redirects=True, headers=H).get(url).text
        except Exception: time.sleep(0.6)
    return ""
def extract(html):
    out,n=[],len(html)
    for mm in re.finditer(r'"usItemId":"(\d+)"', html):
        i=mm.start(); depth=0; start=None; j=i
        while j>=0:
            ch=html[j]
            if ch=='}':depth+=1
            elif ch=='{':
                if depth==0:start=j;break
                depth-=1
            j-=1
        if start is None:continue
        depth=0;k=start
        while k<n:
            ch=html[k]
            if ch=='{':depth+=1
            elif ch=='}':
                depth-=1
                if depth==0:break
            k+=1
        try:
            o=json.loads(html[start:k+1])
            if "name" in o and ("priceInfo" in o or "price" in o): out.append(o)
        except: pass
    return out

cat = "/browse/bebidas-y-snacks/bebidas/13901022_56657077"
base = "https://super.lider.cl" + cat
print("category:", cat)
seen=set()
for pg in [1,2,3,17]:
    for tmpl in [f"{base}?page={pg}", f"{base}?affinityOverride=default&page={pg}"]:
        html=get(tmpl)
        pr=extract(html)
        ids=[p['usItemId'] for p in pr]
        new=[i for i in ids if i not in seen]
        # total count hint
        tc=re.search(r'"totalItemCount[^"]*":(\d+)', html) or re.search(r'(\d+)\s+resultados', html)
        print(f"  {tmpl.split('lider.cl')[1]}: {len(pr)} prods, {len(new)} new, first={pr[0]['name'][:26] if pr else None}, totalHint={tc.group(1) if tc else '?'}")
        seen.update(ids)
        break
print("unique so far:", len(seen))
