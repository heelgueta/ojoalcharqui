"""Instaleap family adapter — Acuenta (Super Bodega Acuenta).

GraphQL API (see DECISIONS.md):
  POST https://nextgentheadless.instaleap.io/api/v3   header Apikey: <key>
  GetCategoryTree         -> getCategory (nested subCategories)
  GetProductsByCategory   -> getProductsByCategory(input{categoryReference,
                             storeReference, clientId, currentPage})
                             -> { pagination{page,pages}, category{products[...]} }

CatalogProductModel exposes clean EANs, brand, price, previousPrice (was-price),
pricePerSubUnit (ppum), subUnit/subQty (grammage), promotion, stock.
"""
from __future__ import annotations

from typing import Iterator

import httpx

from .base import Category, NormProduct, StoreAdapter, clp_to_int

ENDPOINT = "https://nextgentheadless.instaleap.io/api/v3"
MAX_PAGES = 200

_CATEGORY_TREE = """
query GetCategoryTree($i: GetCategoryInput!) {
  getCategory(getCategoryInput: $i) {
    reference name
    subCategories { reference name
      subCategories { reference name
        subCategories { reference name } } }
  }
}"""

_PRODUCTS = """
query GetProductsByCategory($i: GetProductsByCategoryInput!) {
  getProductsByCategory(getProductsByCategoryInput: $i) {
    pagination { page pages }
    category {
      reference name
      products {
        sku ean name brand description
        price previousPrice pricePerSubUnit promotionPricePerSubUnit
        unit subUnit subQty photosUrl slug stock isAvailable
        promotion { type description }
      }
    }
  }
}"""


class InstaleapAdapter:
    platform = "instaleap"

    def __init__(self, slug: str, name: str, origin: str, apikey: str,
                 client_id: str, store_reference: str, endpoint: str = ENDPOINT):
        self.slug = slug
        self.name = name
        self.origin = origin.rstrip("/")
        self.apikey = apikey
        self.client_id = client_id
        self.store_reference = store_reference
        self.endpoint = endpoint
        self.sales_channel = store_reference

    def headers(self) -> dict:
        return {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.origin,
            "Referer": self.origin + "/",
            "Apikey": self.apikey,
        }

    def _post(self, fetch, query: str, variables: dict):
        return fetch("POST", self.endpoint, headers=self.headers(),
                     json={"query": query, "variables": variables})

    # -- categories -------------------------------------------------------
    def categories(self, client: httpx.Client) -> list[Category]:
        r = client.post(self.endpoint, headers=self.headers(),
                        json={"query": _CATEGORY_TREE,
                              "variables": {"i": {"clientId": self.client_id,
                                                  "storeReference": self.store_reference}}})
        r.raise_for_status()
        roots = (r.json().get("data") or {}).get("getCategory") or []
        leaves: list[Category] = []

        def walk(node, name_path, level):
            ref = str(node.get("reference"))
            names = name_path + [node.get("name", "")]
            subs = node.get("subCategories") or []
            if subs:
                for s in subs:
                    walk(s, names, level + 1)
            else:
                leaves.append(Category(category_id=ref, name=" / ".join(names),
                                       slug=ref, level=level))

        for root in roots:
            # skip obvious cross-cutting promo buckets by name? keep all — dedup by sku later
            walk(root, [], 0)
        # de-dup leaves by reference (categories repeat across promo trees)
        uniq = {c.slug: c for c in leaves}
        return list(uniq.values())

    # -- products ---------------------------------------------------------
    def products_in(self, client: httpx.Client, category: Category, fetch) -> Iterator[NormProduct]:
        seen: set[str] = set()
        page, pages = 1, 1
        while page <= pages and page <= MAX_PAGES:
            r = self._post(fetch, _PRODUCTS, {"i": {
                "categoryReference": category.slug,
                "storeReference": self.store_reference,
                "clientId": self.client_id,
                "currentPage": page,
            }})
            if r.status_code != 200:
                break
            data = (r.json().get("data") or {}).get("getProductsByCategory") or {}
            pag = data.get("pagination") or {}
            pages = pag.get("pages") or page
            prods = ((data.get("category") or {}).get("products")) or []
            if not prods:
                break
            fresh = 0
            for raw in prods:
                np = self._normalize(raw, category)
                if np.product_key in seen:
                    continue
                seen.add(np.product_key)
                fresh += 1
                yield np
            if fresh == 0:
                break
            page += 1

    def _normalize(self, raw: dict, category: Category) -> NormProduct:
        eans = raw.get("ean") or []
        ean = next((e for e in eans if e and str(e).isdigit() and len(str(e)) in (13, 12, 8)), None)
        price = clp_to_int(raw.get("price"))
        prev = clp_to_int(raw.get("previousPrice"))
        list_price = prev if (prev and price and prev > price) else price
        photos = raw.get("photosUrl") or []
        img = photos[0] if photos else None
        sub_qty = raw.get("subQty")
        sub_unit = raw.get("subUnit")
        net = f"{sub_qty} {sub_unit}" if sub_qty and sub_unit else None
        promo = raw.get("promotion") or {}

        return NormProduct(
            product_key=str(raw.get("sku")),
            ean=str(ean) if ean else None,
            sku=str(raw.get("sku")) if raw.get("sku") else None,
            name=raw.get("name") or "",
            brand=raw.get("brand") or None,
            description=raw.get("description") or None,
            category_path=category.name,
            category_slug=raw.get("slug") or category.slug,
            measurement_unit=raw.get("unit") or None,
            net_content_raw=net,
            image_url=img,
            available=bool(raw.get("isAvailable", True)),
            price=price,
            list_price=list_price,
            price_no_disc=list_price,
            in_offer=bool(prev and price and prev > price),
            ppum=clp_to_int(raw.get("pricePerSubUnit")),
            ppum_unit=sub_unit,
            saving_text=None,
            promo_text=promo.get("description") or None,
            best_card_price=None,
            card_prices=[],
            raw=raw,
        )


def build_adapters() -> list[StoreAdapter]:
    return [
        InstaleapAdapter(
            slug="acuenta", name="Acuenta",
            origin="https://www.acuenta.cl",
            apikey="70196ab63cc12d4dbfe0c7ca8c3c603cee68db1975702eac2096898f352e",
            client_id="SUPER_BODEGA", store_reference="580",
        ),
    ]
