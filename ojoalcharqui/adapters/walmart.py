"""Walmart family adapter — Lider.

Lider runs on Walmart's "glass" stack (GraphQL `/swag/graphql`), but every
category/browse page server-renders the full product list into the HTML as RSC
flight data. Rather than replicate Walmart's persisted-query GraphQL auth, we
fetch the SSR browse pages and extract the embedded product JSON. (See DECISIONS.)

  category tree: parse /browse/... links from the home (+ department pages)
  browse:        GET /browse/<path>/<idpath>?page=N  -> parse embedded products
                 page until an empty page; dedup by usItemId.
"""
from __future__ import annotations

import json
import re
from typing import Iterator

import httpx

from .base import Category, NormProduct, StoreAdapter, clp_to_int

ORIGIN = "https://super.lider.cl"
MAX_PAGES = 60
_USITEM = re.compile(r'"usItemId":"(\d+)"')
_BROWSE = re.compile(r'"(?:url|clickThrough|value|link)":"(/browse/[a-z0-9][a-z0-9/_\-]+)"', re.I)


def _extract_products(html: str) -> list[dict]:
    """Pull balanced JSON objects that contain a usItemId and look like products."""
    out, n = [], len(html)
    for mm in _USITEM.finditer(html):
        i = mm.start()
        depth, start, j = 0, None, i
        while j >= 0:                       # backtrack to opening brace
            ch = html[j]
            if ch == '}':
                depth += 1
            elif ch == '{':
                if depth == 0:
                    start = j
                    break
                depth -= 1
            j -= 1
        if start is None:
            continue
        depth, k = 0, start
        while k < n:                        # forward to matching close
            ch = html[k]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    break
            k += 1
        try:
            obj = json.loads(html[start:k + 1])
        except Exception:
            continue
        if "name" in obj and ("priceInfo" in obj or "price" in obj):
            out.append(obj)
    return out


def _ean_from_usitem(usitem: str) -> str | None:
    """usItemId embeds a GTIN. Strip leading zeros; accept 13-digit EAN."""
    s = usitem.lstrip("0")
    return s if len(s) == 13 and s.isdigit() else None


class WalmartAdapter:
    platform = "walmart-glass"

    def __init__(self, slug: str, name: str, origin: str = ORIGIN):
        self.slug = slug
        self.name = name
        self.origin = origin.rstrip("/")
        self.sales_channel = "super"

    def headers(self) -> dict:
        return {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
            "Referer": self.origin + "/",
        }

    # -- categories -------------------------------------------------------
    def categories(self, client: httpx.Client) -> list[Category]:
        r = client.get(self.origin + "/", headers=self.headers())
        r.raise_for_status()
        links = sorted(set(_BROWSE.findall(r.text)))
        # keep the most specific paths; drop a parent if a child path extends it
        cats = []
        for ln in links:
            idpath = ln.rstrip("/").split("/")[-1]      # e.g. 13901022_56657077
            name = " / ".join(ln.split("/")[2:-1]) or ln
            cats.append(Category(category_id=idpath, name=name, slug=ln, level=ln.count("/") - 2))
        return cats

    # -- products ---------------------------------------------------------
    def products_in(self, client: httpx.Client, category: Category, fetch) -> Iterator[NormProduct]:
        seen: set[str] = set()
        empty_streak = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{self.origin}{category.slug}?page={page}"
            r = fetch("GET", url, headers=self.headers())
            if r.status_code != 200:
                break
            prods = _extract_products(r.text)
            if not prods:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue
            empty_streak = 0
            fresh = 0
            for raw in prods:
                uid = str(raw.get("usItemId"))
                if uid in seen:
                    continue
                seen.add(uid)
                fresh += 1
                yield self._normalize(raw, category)
            if fresh == 0:
                break

    def _normalize(self, raw: dict, category: Category) -> NormProduct:
        uid = str(raw.get("usItemId"))
        pi = raw.get("priceInfo") or {}
        price = clp_to_int(pi.get("linePrice")) or clp_to_int(raw.get("price"))
        was = clp_to_int(pi.get("wasPrice"))
        list_price = was or clp_to_int(pi.get("itemPrice")) or price
        unit_price = pi.get("unitPrice") or ""              # "$1.590 x lt"
        ppum = clp_to_int(unit_price.split("x")[0]) if "x" in unit_price else None
        ppum_unit = unit_price.split("x")[-1].strip() if "x" in unit_price else None

        img = (raw.get("imageInfo") or {}).get("thumbnailUrl")
        if img and "?" in img:
            img = img.split("?")[0]
        cat = raw.get("category") or {}
        avail = raw.get("availabilityStatusV2") or raw.get("availabilityStatus")
        out_of_stock = bool(raw.get("isOutOfStock"))

        return NormProduct(
            product_key=uid,
            ean=_ean_from_usitem(uid),
            sku=uid,
            name=raw.get("name") or "",
            brand=raw.get("brand") or None,
            description=raw.get("shortDescription") or None,
            category_path=cat.get("categoryPath"),
            category_slug=category.slug,
            measurement_unit=raw.get("salesUnit") or None,
            net_content_raw=None,                          # parsed from name
            image_url=img,
            available=not out_of_stock,
            price=price,
            list_price=list_price,
            price_no_disc=list_price,
            in_offer=bool(price and list_price and price < list_price),
            ppum=ppum,
            ppum_unit=ppum_unit,
            saving_text=pi.get("savings") or None,
            promo_text=None,
            best_card_price=None,
            card_prices=[],
            raw=raw,
        )


def build_adapters() -> list[StoreAdapter]:
    return [WalmartAdapter("lider", "Líder", ORIGIN)]
