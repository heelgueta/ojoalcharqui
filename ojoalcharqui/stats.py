"""Descriptive statistics over the latest run of each store.

Pure-Python (no numpy) so the app stays dependency-light. Everything is computed
on the most recent ok/partial run per store. Designed for the research/SERNAC
angle: distributions, central tendency + spread, coverage, and breakdowns by
category and brand.
"""
from __future__ import annotations

import math
import sqlite3
from collections import Counter, defaultdict

from . import config


def _open(slug: str) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{config.db_path(slug)}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _latest_run(con) -> str | None:
    r = con.execute("SELECT run_id FROM runs WHERE status IN ('ok','partial') "
                    "ORDER BY started_at DESC LIMIT 1").fetchone()
    return r["run_id"] if r else None


# -- descriptive helpers --------------------------------------------------
def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        return 0.0
    if len(sorted_xs) == 1:
        return float(sorted_xs[0])
    pos = q * (len(sorted_xs) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_xs[lo])
    frac = pos - lo
    return sorted_xs[lo] * (1 - frac) + sorted_xs[hi] * frac


def describe(xs: list[float]) -> dict:
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n == 0:
        return {"n": 0}
    s = sorted(xs)
    mean = sum(s) / n
    var = sum((x - mean) ** 2 for x in s) / (n - 1) if n > 1 else 0.0
    q1, med, q3 = _quantile(s, .25), _quantile(s, .5), _quantile(s, .75)
    return {
        "n": n, "mean": mean, "sd": math.sqrt(var),
        "min": s[0], "max": s[-1], "median": med, "q1": q1, "q3": q3,
        "iqr": q3 - q1,
        "cv": (math.sqrt(var) / mean) if mean else 0.0,
    }


def histogram(xs: list[float], bins: int = 28, log: bool = True) -> dict:
    """Bucket counts for a bar chart. Log-spaced by default (prices are heavy-tailed)."""
    xs = [x for x in xs if x and x > 0]
    if not xs:
        return {"bins": [], "max_count": 0, "log": log}
    lo, hi = min(xs), max(xs)
    if log:
        a, b = math.log10(lo), math.log10(hi if hi > lo else lo * 10)
        edges = [10 ** (a + (b - a) * i / bins) for i in range(bins + 1)]
    else:
        edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = [0] * bins
    for x in xs:
        # find bucket
        placed = False
        for i in range(bins):
            if x <= edges[i + 1] or i == bins - 1:
                counts[i] += 1
                placed = True
                break
        if not placed:
            counts[-1] += 1
    out = [{"lo": edges[i], "hi": edges[i + 1], "count": counts[i]} for i in range(bins)]
    return {"bins": out, "max_count": max(counts), "log": log}


# -- per-store summary ----------------------------------------------------
def store_summary(slug: str) -> dict:
    con = _open(slug)
    run = _latest_run(con)
    if not run:
        con.close()
        return {"slug": slug, "empty": True}

    rows = con.execute("""
        SELECT p.brand, p.category_path, p.ean, p.grammage_base, p.grammage_base_unit,
               o.price, o.list_price, o.in_offer, o.best_card_price, o.unit_price_calc
        FROM products p
        JOIN observations o ON o.obs_id = (
            SELECT obs_id FROM observations ox WHERE ox.product_key = p.product_key
            ORDER BY captured_at DESC, obs_id DESC LIMIT 1)
        WHERE p.last_seen_run = ?""", (run,)).fetchall()
    meta = {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM meta")}
    run_row = dict(con.execute("SELECT * FROM runs WHERE run_id=?", (run,)).fetchone())
    con.close()

    n = len(rows)
    prices = [r["price"] for r in rows if r["price"]]
    n_offer = sum(1 for r in rows if r["in_offer"])
    n_ean = sum(1 for r in rows if r["ean"])
    n_gram = sum(1 for r in rows if r["grammage_base"])
    n_card = sum(1 for r in rows if r["best_card_price"])

    # offer discount depths
    disc = []
    for r in rows:
        if r["in_offer"] and r["list_price"] and r["price"] and r["list_price"] > r["price"]:
            disc.append((r["list_price"] - r["price"]) / r["list_price"] * 100)

    # by-category (top by count)
    cat_acc: dict[str, list] = defaultdict(list)
    for r in rows:
        top = _top_cat(r["category_path"])
        if r["price"]:
            cat_acc[top].append((r["price"], r["in_offer"]))
    cats = []
    for name, lst in cat_acc.items():
        ps = [p for p, _ in lst]
        cats.append({
            "name": name, "n": len(lst),
            "median": _quantile(sorted(ps), .5),
            "mean": sum(ps) / len(ps),
            "offer_rate": sum(1 for _, o in lst if o) / len(lst) * 100,
        })
    cats.sort(key=lambda c: c["n"], reverse=True)

    # brand leaderboard
    brands = Counter(r["brand"] for r in rows if r["brand"]).most_common(15)

    # unit price by base unit (g/ml/un not comparable across)
    upc_by_unit: dict[str, list] = defaultdict(list)
    for r in rows:
        if r["unit_price_calc"] and r["grammage_base_unit"]:
            upc_by_unit[r["grammage_base_unit"]].append(r["unit_price_calc"])

    return {
        "slug": slug, "name": meta.get("store_name", slug.title()),
        "platform": meta.get("platform", ""),
        "run": run_row, "n": n,
        "price": describe(prices),
        "hist": histogram(prices),
        "offer_rate": (n_offer / n * 100) if n else 0,
        "ean_cov": (n_ean / n * 100) if n else 0,
        "gram_cov": (n_gram / n * 100) if n else 0,
        "card_cov": (n_card / n * 100) if n else 0,
        "discount_depth": describe(disc),
        "categories": cats[:18],
        "brands": [{"name": b, "n": c} for b, c in brands],
        "upc_units": {u: describe(v) for u, v in upc_by_unit.items()},
    }


def _top_cat(path: str | None) -> str:
    if not path:
        return "—"
    parts = [p for p in path.strip("/").split("/") if p]
    return parts[0] if parts else "—"


# -- cross-store overview -------------------------------------------------
def overview() -> list[dict]:
    out = []
    for path in sorted(config.DATA_DIR.glob("*.sqlite")):
        slug = path.stem
        if slug.startswith("_"):
            continue
        try:
            s = store_summary(slug)
        except Exception:
            continue
        if s.get("empty"):
            continue
        out.append({
            "slug": slug, "name": s["name"], "n": s["n"],
            "median": s["price"].get("median"), "mean": s["price"].get("mean"),
            "sd": s["price"].get("sd"), "offer_rate": s["offer_rate"],
            "ean_cov": s["ean_cov"], "gram_cov": s["gram_cov"],
        })
    out.sort(key=lambda r: r["n"], reverse=True)
    return out
