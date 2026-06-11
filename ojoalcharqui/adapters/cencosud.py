"""Cencosud family adapter — Jumbo (and Santa Isabel, same platform).

Platform recipe (see DECISIONS.md):
  base   https://sm-web-api.ecomm.cencosud.com/catalog/api/v1
  header apikey: <per-store catalog key>
  tree   GET /catalog_system/pub/category/tree/50?sc=<sc>
  browse GET /products/search/?fq=C:/<catId>/&page=N&sc=<sc>   (12/page, fixed)

No EAN is exposed here (only internal referenceId), so cross-family matching
falls back to fuzzy name/brand/grammage.
"""
from __future__ import annotations

from typing import Iterator

import httpx

from .base import Category, NormProduct, StoreAdapter, clp_to_int

CENCOSUD_BASE = "https://sm-web-api.ecomm.cencosud.com/catalog/api/v1"
PER_PAGE = 12          # fixed by the API
MAX_PAGES = 350        # safety ceiling per category (~4200 products)


class CencosudAdapter:
    platform = "cencosud-sm"

    def __init__(self, slug: str, name: str, origin: str, apikey: str,
                 sc: str = "1", base: str = CENCOSUD_BASE):
        self.slug = slug
        self.name = name
        self.origin = origin.rstrip("/")
        self.apikey = apikey
        self.sc = str(sc)
        self.base = base.rstrip("/")
        self.sales_channel = self.sc

    def headers(self) -> dict:
        return {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CL,es;q=0.9",
            "Origin": self.origin,
            "Referer": self.origin + "/",
            "apikey": self.apikey,
        }

    # -- categories -------------------------------------------------------
    def categories(self, client: httpx.Client) -> list[Category]:
        r = client.get(f"{self.base}/catalog_system/pub/category/tree/50",
                       params={"sc": self.sc}, headers=self.headers())
        r.raise_for_status()
        tree = r.json()
        leaves: list[Category] = []

        def walk(node, id_path, name_path, level):
            cid = str(node.get("id"))
            path = id_path + [cid]
            names = name_path + [node.get("name", "")]
            children = node.get("children") or []
            if children:
                for ch in children:
                    walk(ch, path, names, level + 1)
            else:
                leaves.append(Category(
                    category_id=cid,
                    name=" / ".join(names),
                    slug="/".join(path),           # numeric path e.g. "1/3"
                    parent_slug="/".join(id_path) or None,
                    level=level,
                ))

        for top in tree:
            walk(top, [], [], 0)
        return leaves

    # -- products ---------------------------------------------------------
    def products_in(self, client: httpx.Client, category: Category, fetch) -> Iterator[NormProduct]:
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            r = fetch("GET", f"{self.base}/products/search/",
                      params={"fq": f"C:/{category.slug}/", "page": page, "sc": self.sc},
                      headers=self.headers())
            if r.status_code != 200:
                break
            data = r.json()
            items = data if isinstance(data, list) else data.get("products", [])
            if not items:
                break
            fresh = 0
            for raw in items:
                np = self._normalize(raw, category)
                if not np or np.product_key in seen:
                    continue
                seen.add(np.product_key)
                fresh += 1
                yield np
            if len(items) < PER_PAGE or fresh == 0:
                break

    def _normalize(self, raw: dict, category: Category) -> NormProduct | None:
        items = raw.get("items") or []
        if not items:
            return None
        it = items[0]
        sellers = it.get("sellers") or []
        offer = (sellers[0].get("commertialOffer") if sellers else {}) or {}

        price = clp_to_int(offer.get("Price"))
        list_price = clp_to_int(offer.get("ListPrice"))
        avail_qty = offer.get("AvailableQuantity", 0)

        ref = None
        for r in it.get("referenceId") or []:
            if r.get("Key") in ("RefId", "EAN") and r.get("Value"):
                ref = r["Value"]
        # 13-digit numeric -> treat as EAN; else keep as internal ref
        ean = ref if (ref and ref.isdigit() and len(ref) == 13) else None

        images = it.get("images") or []
        img = images[0].get("imageUrl") if images else None

        cats = raw.get("categories") or []
        cat_path = cats[0] if cats else None

        return NormProduct(
            product_key=str(raw.get("productId")),
            ean=ean,
            sku=str(it.get("itemId")) if it.get("itemId") else None,
            name=raw.get("productName") or "",
            brand=raw.get("brand") or None,
            description=raw.get("productName") or None,
            category_path=cat_path,
            category_slug=raw.get("linkText") or category.slug,
            measurement_unit=it.get("measurementUnit") or None,
            net_content_raw=None,           # not provided; grammage parsed from name
            image_url=img,
            available=bool(avail_qty and avail_qty > 0),
            price=price,
            list_price=list_price,
            price_no_disc=clp_to_int(offer.get("PriceWithoutDiscount")),
            in_offer=bool(price and list_price and price < list_price),
            ppum=None,
            ppum_unit=None,
            saving_text=None,
            promo_text=None,
            best_card_price=None,
            card_prices=[],
            raw=raw,
        )


def build_adapters() -> list[StoreAdapter]:
    return [
        CencosudAdapter(
            slug="jumbo", name="Jumbo",
            origin="https://www.jumbo.cl",
            apikey="WlVnnB7c1BblmgUPOfg", sc="1",
        ),
    ]
