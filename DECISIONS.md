# Decisions & weird shit log

Running notes on non-obvious choices and the strange behaviour of each store's
API. Append-only-ish; newest stuff at the bottom of each section.

## Architecture

- **One SQLite per store**, append-only `observations` fact table. Rationale and
  schema in [ojoalcharqui/db.py](ojoalcharqui/db.py). Merge-friendly via UUID
  run ids so two people's DBs union without collision (`StoreDB.merge_from`).
- **Politeness lives in the request rate, not the User-Agent.** We tried an
  honest `ojoalcharqui/0.1` UA and the WAFs 403'd it instantly. A realistic
  browser UA is mandatory just to be served. So: browser UA, but slow + serial +
  backoff. (Documented inline in each adapter.)
- **Location**: v1 pins one Santiago sales channel per chain and records it on
  every run. Multi-comuna sweep is a later toggle (prices *are* comuna-dependent
  in CL, but we validate the pipeline on one location first).
- **Grammage** parsed to a base unit (g/ml/un) at write time so unit prices are
  comparable and shrinkflation (grammage drop at same price) is detectable.

## Platform families (one adapter per family, two stores each)

| Family    | Stores              | Status |
|-----------|---------------------|--------|
| SMU BFF   | Unimarc, Alvi       | Unimarc ✅ / Alvi ⚠ (BFF differs, TODO) |
| Cencosud  | Jumbo, Santa Isabel | Jumbo ✅ / Santa Isabel (same base, TODO) |
| Walmart   | Lider, Acuenta      | TODO |

## SMU (Unimarc / Alvi)

- Pagination is `from`/`to` as **strings** in a 50-window; integers are silently
  ignored. `page`/`size`/`offset` do nothing. Cost an hour. See recon/FINDINGS.
- `categories` param = browse filter; `slug` param = search box (relevance, no
  paging). Different beasts.
- Headers `version: 1.0.0` (format-validated only) and `source: web` required.
- Alvi's BFF host `bff-alvi-web.alvi.cl` 400s on `/catalog/categories` — it is
  NOT a drop-in of Unimarc's BFF. Deferred (not a priority store).

## Cencosud (Jumbo / Santa Isabel)

- The public VTEX routes (`/api/catalog_system/...`, intelligent-search) all
  return **410 Gone** — Cencosud killed them and proxies through an Apigee
  gateway that needs a per-service `apikey` header.
- Frontend is a webpack app on `assets-jumbo.ecomm.cencosud.com`. The API base
  map and the per-service apikeys are embedded in the JS bundle (chunk `8434`).
  We extract them in recon (`recon/jumbo11.py`). Catalog apikey: `WlVnnB7c1BblmgUPOfg`.
- The gateway is picky about **which host the key is valid for**:
  - `bff.jumbo.cl/catalog` → "Invalid authentication credentials" (different key)
  - `sm-web-api.ecomm.cencosud.com/catalog/api/v1` → ✅ works with the catalog key.
- Working recipe (Jumbo, sc=1):
  - base `https://sm-web-api.ecomm.cencosud.com/catalog/api/v1`, header `apikey: WlVnnB7c1BblmgUPOfg`
  - category tree: `GET /catalog_system/pub/category/tree/50?sc=1`
  - browse: `GET /products/search/?fq=C:/<catId>/&page=N&sc=1` (12 products/page, fixed; no page-size override works)
  - product: `items[].sellers[].commertialOffer.{Price,ListPrice,PriceWithoutDiscount,AvailableQuantity}`, `items[].images[].imageUrl`, `items[].referenceId`.
- **No EAN exposed** on this endpoint (only an internal `referenceId`/RefId like
  `1858600`). Consequence: Jumbo↔SMU cross-store matching can't use EAN; it'll
  need fuzzy brand+name+grammage matching (planned). Within Cencosud
  (Jumbo↔Santa Isabel) productId/refId may align.
- `sm-web-api.ecomm.cencosud.com` is the shared SM platform → Santa Isabel
  should be the same base with its own sc + apikey + Origin. TODO.
