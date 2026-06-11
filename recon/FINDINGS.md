# Recon: Chilean supermarket e-commerce platforms

Three platform families cover the six big supermarket chains. One adapter per
family covers two stores each.

| Chain        | Holding   | Platform family | Status |
|--------------|-----------|-----------------|--------|
| Unimarc      | SMU       | SMU BFF         | ✅ solved |
| Alvi         | SMU       | SMU BFF         | ✅ solved (same shape) |
| Jumbo        | Cencosud  | SMdigital       | lead, TODO |
| Santa Isabel | Cencosud  | SMdigital + Constructor.io | lead, TODO |
| Lider        | Walmart   | Walmart "pegasus" API | lead, TODO |
| Acuenta      | Walmart   | Instaleap       | lead, TODO |

## SMU family (Unimarc, Alvi) — SOLVED

BFF host:
- Unimarc: `https://bff-unimarc-ecommerce.unimarc.cl`
- Alvi:    `https://bff-alvi-web.alvi.cl` (parity to confirm at build time)

Required headers on every call:
```
version: 1.0.0          # must match \d+\.\d+\.\d+, value irrelevant
source:  web            # enum: web | ios | android | web-mobile
Origin/Referer: store homepage
```

### Category tree
`GET /catalog/categories` → JSON array of top categories, each with
`{id, name, slug, description, imageUrl, subcategories:[...]}`, 2–3 levels deep.
Leaf nodes are what we enumerate.

### Product listing (paginated)
`POST /catalog/product/search`
```json
{ "categories": "<category-slug>", "from": "0", "to": "49", "salesChannel": "1" }
```
- `from`/`to` are **strings** and are the real pagination window (inclusive).
  Integers are silently ignored — this cost an hour to discover.
- `page`/`size`/`offset` are all ignored.
- Walk windows of 50 until a window returns < 50 rows.
- Response: `{ availableProducts:[...], notAvailableProducts:[...], resource, ... }`
- `categories` is a *browse* filter (exact category). `slug` (different param)
  is the *search box* (relevance mode, ignores pagination).

### Per-product fields (rich)
`product.item`: `itemId, sku, ean, name, nameComplete, brand, brandId,
description, categoryId, categories[], categorySlug, netContent ("1 Kg"),
measurementUnit, measurementUnitUn, unitMultiplier, images[]`

`product.price`: `price ("$1.000"), listPrice, priceWithoutDiscount,
inOffer (bool), ppum ("$1.000 x Kg"), ppumListPrice, saving ("Ahorras $390")`

`product.promotion.pricePaymentsMethods[]`: card/club prices, each
`{ namePromotion, paymentMethod, price (int), pPum, descriptionMessage, saving }`
→ this is the *precio con tarjeta / socio* dimension.

Prices come as formatted CLP strings ("$1.000"); parse to int.

## Cencosud family (Jumbo, Santa Isabel) — lead
- Server header `nginx, Cencosud`; assets on `assets-jumbo.ecomm.cencosud.com`.
- Backend fingerprint `smdigital`; Santa Isabel search via Constructor.io
  (`_constructorio_search_client_id`).
- TODO: find product endpoint + key (likely `api*.smdigital.cl` or a
  Cencosud ecomm host; Constructor.io autocomplete/browse for Santa Isabel).

## Walmart family (Lider, Acuenta) — lead
- Lider: Next.js + `developer.api.us.walmart.com/api-proxy/service/pegasus/be/v7`,
  images on `i5.walmartimages.cl`. Google API keys embedded (Firebase, not catalog).
- Acuenta: Instaleap (`wanda-files.instaleap.io`, `SUPER_BODEGA` tenant).
- TODO: pegasus GraphQL/REST product query; Instaleap catalog API + client id.

## Location / comuna
Prices are location-dependent. `salesChannel` selects the price list; the BFF
infers location from address/session. For v1 we pin one canonical Santiago
sales channel and record it on every run. Multi-comuna sweep is a later toggle.
