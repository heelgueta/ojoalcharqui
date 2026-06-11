"""SMU family adapter — Unimarc and Alvi.

Platform recipe (see recon/FINDINGS.md):
  GET  {bff}/catalog/categories                      -> category tree
  POST {bff}/catalog/product/search                  -> paginated products
       body {categories: slug, from: "0", to: "49", salesChannel: "1"}
       headers version:1.0.0 source:web
"""
from __future__ import annotations

from typing import Iterator

import httpx

from .base import Category, NormProduct, StoreAdapter, clp_to_int

PAGE = 50          # window size; API caps at 50 regardless
MAX_WINDOWS = 60   # safety: 3000 products per category ceiling


class SMUAdapter:
    platform = "smu-bff"

    def __init__(self, slug: str, name: str, bff: str, origin: str, sales_channel: str = "1"):
        self.slug = slug
        self.name = name
        self.bff = bff.rstrip("/")
        self.origin = origin.rstrip("/")
        self.sales_channel = sales_channel

    def headers(self) -> dict:
        # A realistic browser UA is required: the WAF 403s non-browser agents.
        # Politeness lives in the request rate (see engine.py), not in the UA.
        return {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-CL,es;q=0.9",
            "Origin": self.origin,
            "Referer": self.origin + "/",
            "Content-Type": "application/json",
            "version": "1.0.0",
            "source": "web",
        }

    # -- categories -------------------------------------------------------
    def categories(self, client: httpx.Client) -> list[Category]:
        r = client.get(f"{self.bff}/catalog/categories", headers=self.headers())
        r.raise_for_status()
        tree = r.json()
        leaves: list[Category] = []

        def walk(node, parent_slug, level):
            slug = node.get("slug")
            subs = node.get("subcategories") or []
            cat = Category(
                category_id=str(node.get("id")),
                name=node.get("name", ""),
                slug=slug,
                parent_slug=parent_slug,
                level=level,
            )
            if subs:
                for s in subs:
                    walk(s, slug, level + 1)
            else:
                if slug:
                    leaves.append(cat)

        for top in tree:
            # skip the synthetic "Ofertas" bucket (ids in the 999xxx range) —
            # those products also appear under their real categories
            if str(top.get("id", "")).startswith("999"):
                continue
            walk(top, None, 0)
        return leaves

    # -- products ---------------------------------------------------------
    def products_in(self, client: httpx.Client, category: Category, fetch) -> Iterator[NormProduct]:
        seen: set[str] = set()
        for w in range(MAX_WINDOWS):
            lo = w * PAGE
            body = {
                "categories": category.slug,
                "from": str(lo),
                "to": str(lo + PAGE - 1),
                "salesChannel": self.sales_channel,
            }
            r = fetch("POST", f"{self.bff}/catalog/product/search",
                      headers=self.headers(), json=body)
            if r.status_code != 200:
                break
            items = r.json().get("availableProducts", []) or []
            if not items:
                break
            fresh = 0
            for raw in items:
                np = self._normalize(raw, category)
                if np.product_key in seen:
                    continue
                seen.add(np.product_key)
                fresh += 1
                yield np
            if len(items) < PAGE:
                break
            if fresh == 0:           # API ignored the window -> stop, no progress
                break

    def _normalize(self, raw: dict, category: Category) -> NormProduct:
        item = raw.get("item", {}) or {}
        price = raw.get("price", {}) or {}
        promo = raw.get("promotion", {}) or {}

        cards = []
        for pm in promo.get("pricePaymentsMethods", []) or []:
            cards.append({
                "payment_method": pm.get("paymentMethod"),
                "promo_name": pm.get("namePromotion"),
                "price": clp_to_int(pm.get("price")),
                "ppum": pm.get("pPum"),
                "saving": pm.get("saving"),
            })
        best_card = min((c["price"] for c in cards if c["price"]), default=None)

        cats = item.get("categories") or []
        cat_path = cats[0] if cats else None

        ppum_raw = price.get("ppum") or ""          # "$1.000 x Kg"
        ppum_unit = ppum_raw.split("x")[-1].strip() if "x" in ppum_raw else None

        avail = price.get("availableQuantity")
        available = True if avail is None else avail > 0

        return NormProduct(
            product_key=str(item.get("itemId") or item.get("sku")),
            ean=(item.get("ean") or None),
            sku=str(item.get("sku")) if item.get("sku") else None,
            name=item.get("name") or item.get("nameComplete") or "",
            brand=item.get("brand") or None,
            brand_id=str(item.get("brandId")) if item.get("brandId") else None,
            description=item.get("description") or None,
            category_path=cat_path,
            category_slug=item.get("categorySlug") or category.slug,
            measurement_unit=item.get("measurementUnit") or None,
            net_content_raw=item.get("netContent") or None,
            image_url=(item.get("images") or [None])[0],
            available=available,
            price=clp_to_int(price.get("price")),
            list_price=clp_to_int(price.get("listPrice")),
            price_no_disc=clp_to_int(price.get("priceWithoutDiscount")),
            in_offer=bool(price.get("inOffer")),
            ppum=clp_to_int(ppum_raw),
            ppum_unit=ppum_unit,
            saving_text=price.get("saving") or None,
            promo_text=promo.get("name") or promo.get("descriptionMessage") or None,
            card_prices=[c for c in cards if c["price"]],
            best_card_price=best_card,
            raw=raw,
        )


def build_adapters() -> list[StoreAdapter]:
    return [
        SMUAdapter("unimarc", "Unimarc",
                   "https://bff-unimarc-ecommerce.unimarc.cl", "https://www.unimarc.cl"),
        SMUAdapter("alvi", "Alvi",
                   "https://bff-alvi-web.alvi.cl", "https://www.alvi.cl"),
    ]
