"""Store adapter interface.

An adapter knows how to talk to one platform family and yields *normalized*
products. The engine handles politeness, persistence and run bookkeeping, so
adapters stay thin: enumerate categories, page through them, normalize.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterator, Protocol

import httpx


def clp_to_int(s) -> int | None:
    """'$1.390' / '1.390' / 1390 -> 1390."""
    if s is None or s == "":
        return None
    if isinstance(s, (int, float)):
        return int(s)
    digits = re.sub(r"[^\d]", "", str(s))
    return int(digits) if digits else None


@dataclass
class NormProduct:
    """Platform-agnostic product + its current price observation."""
    product_key: str
    ean: str | None = None
    sku: str | None = None
    name: str = ""
    brand: str | None = None
    brand_id: str | None = None
    description: str | None = None
    category_path: str | None = None
    category_slug: str | None = None
    measurement_unit: str | None = None
    net_content_raw: str | None = None
    image_url: str | None = None
    # price observation
    available: bool = True
    price: int | None = None
    list_price: int | None = None
    price_no_disc: int | None = None
    in_offer: bool = False
    ppum: int | None = None
    ppum_unit: str | None = None
    saving_text: str | None = None
    promo_text: str | None = None
    best_card_price: int | None = None
    card_prices: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class Category:
    category_id: str
    name: str
    slug: str
    parent_slug: str | None = None
    level: int = 0


class StoreAdapter(Protocol):
    slug: str
    name: str
    platform: str

    def categories(self, client: httpx.Client) -> list[Category]:
        """Return the (leaf) categories to enumerate."""
        ...

    def products_in(self, client: httpx.Client, category: Category,
                    fetch) -> Iterator[NormProduct]:
        """Yield normalized products for one category. ``fetch`` is the engine's
        polite request callable: fetch(method, url, **kwargs) -> httpx.Response."""
        ...
