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

## Data quality: the biggest "gaps" are often errors

The Comparador's headline (largest price gaps) is exactly where bad data surfaces,
because mismatches *look* like huge gaps. Two hazards, both handled in
`compare_by_ean`:

1. **Intra-store EAN collisions** — a store occasionally puts the wrong EAN on a
   product (e.g. Acuenta tagged a single yoghurt with a 6-pack's EAN → a fake
   $650-vs-$2750 "gap"). Rare (~2/4300 EANs at Acuenta) but loud. We keep, per
   store, the candidate whose *name* best agrees with the other stores.
2. **Cross-store name disagreement** — if the matched products' names clearly
   aren't the same thing, the source EAN is wrong. We flag those `suspect`
   (name-token Jaccard < 0.34) and hide them by default.

After the guard, top gaps are real (e.g. Acuenta, a hard-discounter with "luka"
round-price lines, genuinely 150–215% cheaper than Unimarc on some SKUs).

## Platform families (one adapter per family, two stores each)

| Family    | Stores              | Status |
|-----------|---------------------|--------|
| SMU BFF   | Unimarc, Alvi       | Unimarc ✅ / Alvi ⚠ (BFF differs, TODO) |
| Cencosud  | Jumbo, Santa Isabel | Jumbo ✅ / Santa Isabel (same base, TODO) |
| Walmart   | Lider               | Lider ✅ (SSR scrape) |
| Instaleap | Acuenta             | Acuenta ✅ (GraphQL) |

Note: Lider and Acuenta are *both* Walmart-owned but run on different stacks
(Lider = Walmart "glass"; Acuenta = Instaleap), so they're separate adapters.

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
- **Santa Isabel — deferred.** Its bundle exposes the *same* catalog apikey
  `WlVnnB7c1BblmgUPOfg`, but on `sm-web-api` that key is bound to the **Jumbo**
  VTEX account: every response says `sellerName: "Jumbo Chile"`, and `sc` only
  switches price lists *within* Jumbo (sc=3/11 give different prices, same
  seller). So SI's real catalog is routed by a mechanism we haven't pinned
  (different base host or an account header). Not a priority store → parked;
  recon scripts in `recon/santaisabel*.py` for whoever resumes it.

## Walmart (Lider)

- Lider runs Walmart's "glass" stack: product data comes from `/swag/graphql`
  with persisted-query hashes + a pile of auth headers (`wm_consumer`,
  `x-o-platform`, traceparent…). Replicating that is brittle.
- BUT every `/browse/...` category page **server-renders the full product list**
  into the HTML as RSC flight data. So we skip GraphQL entirely and parse the
  embedded product JSON from the SSR page (`_extract_products` walks balanced
  braces around each `"usItemId"`).
- Recipe: harvest `/browse/<dept>/<sub>/<idpath>` links from the home; for each,
  `GET {url}?page=N`, parse products, dedup by `usItemId`, page until 2 empty
  pages. ~45 products/page; pages overlap slightly (a pinned first item) — dedup
  handles it.
- Fields: `usItemId` (a GTIN-14), name, brand, `priceInfo{itemPrice, linePrice,
  wasPrice, unitPrice "$X x lt", savings}`, `price` (int = linePrice),
  `imageInfo.thumbnailUrl`, `category.categoryPath`, `isOutOfStock`.
- EAN: `usItemId` is GTIN-14; we accept it as EAN only when stripping leading
  zeros yields exactly 13 digits (imperfect — many are car/non-grocery GTINs).
- Coverage caveat: we browse only the category links exposed on the home page.
  Deeper leaves not linked there are missed in v1. Browsing a parent returns its
  whole subtree, so top/mid-level links still cover most of the catalog.

## Instaleap (Acuenta)

- Acuenta = Instaleap headless storefront. clientId `SUPER_BODEGA`, store `580`.
- Single GraphQL endpoint for all Instaleap tenants:
  `POST https://nextgentheadless.instaleap.io/api/v3`, header `Apikey: <key>`.
  The tenant is selected by the apikey (found in the JS bundle:
  `70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e`).
- Introspection is disabled, so we discovered the schema by crafting queries and
  reading Apollo's "did you mean" field-suggestion errors (recon/acuenta9-14).
- Recipe:
  - tree: `GetCategoryTree` → `getCategory(getCategoryInput:{clientId, storeReference})`
    returns nested `subCategories`.
  - products: `getProductsByCategory(getProductsByCategoryInput:{categoryReference,
    storeReference, clientId, currentPage})` → `{pagination{page,pages}, category{products}}`.
    Pagination field is **`currentPage`** (top-level on the input, not a nested
    `pagination` object — that mislead cost a few tries). Walk 1..pages.
- `CatalogProductModel` is rich: `ean` (array of clean EAN-13!), brand, price,
  `previousPrice` (was-price for offers), `pricePerSubUnit` (ppum), `subUnit`/
  `subQty` (grammage), `promotion`, `stock`, `photosUrl`. **100% EAN coverage**
  in testing → best store for cross-store matching.
