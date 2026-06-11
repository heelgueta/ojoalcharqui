"""Read-side analytics over the per-store SQLite files.

Each store is its own DB, so cross-store questions (comparador) open several and
join in Python by EAN. Single-store questions (price history, fake discounts,
shrinkflation) run straight SQL.
"""
from __future__ import annotations

import csv
import io
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from . import config, adapters


# -- discovery ------------------------------------------------------------
def available_stores() -> list[dict]:
    """Stores that have a DB on disk, plus their headline stats."""
    out = []
    for path in sorted(config.DATA_DIR.glob("*.sqlite")):
        slug = path.stem
        if slug.startswith("_"):       # central/internal DBs (e.g. _catalog) are not stores
            continue
        try:
            con = _open(slug)
            meta = {r["key"]: r["value"] for r in con.execute("SELECT key,value FROM meta")}
            last = con.execute(
                "SELECT * FROM runs WHERE status IN ('ok','partial') ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            n_products = con.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
            n_runs = con.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
            n_obs = con.execute("SELECT COUNT(*) c FROM observations").fetchone()["c"]
            con.close()
        except Exception:
            continue
        if not meta.get("store_slug"):   # not a store DB
            continue
        out.append({
            "slug": slug,
            "name": meta.get("store_name", slug.title()),
            "platform": meta.get("platform", ""),
            "n_products": n_products,
            "n_runs": n_runs,
            "n_observations": n_obs,
            "last_run_at": last["started_at"] if last else None,
            "last_status": last["status"] if last else None,
        })
    return out


def known_stores() -> list[dict]:
    """All stores we *can* scrape, whether or not a DB exists yet."""
    have = {s["slug"]: s for s in available_stores()}
    rows = []
    for a in adapters.all_adapters():
        base = {"slug": a.slug, "name": a.name, "platform": a.platform,
                "n_products": 0, "n_runs": 0, "last_run_at": None, "last_status": None}
        rows.append({**base, **have.get(a.slug, {})})
    return rows


def _open(slug: str) -> sqlite3.Connection:
    path = config.db_path(slug)
    if not path.exists():
        raise FileNotFoundError(path)
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


# -- runs ledger ----------------------------------------------------------
def all_runs() -> list[dict]:
    rows = []
    for s in available_stores():
        con = _open(s["slug"])
        for r in con.execute("SELECT * FROM runs ORDER BY started_at DESC"):
            d = dict(r)
            d["store_name"] = s["name"]
            rows.append(d)
        con.close()
    rows.sort(key=lambda r: r["started_at"], reverse=True)
    return rows


# -- search & product detail ---------------------------------------------
def search_products(slug: str, q: str = "", limit: int = 60, offset: int = 0,
                    only_offers: bool = False) -> list[dict]:
    con = _open(slug)
    where, params = ["1=1"], []
    if q:
        where.append("(p.name LIKE ? OR p.brand LIKE ? OR p.ean = ?)")
        params += [f"%{q}%", f"%{q}%", q]
    if only_offers:
        where.append("o.in_offer = 1")
    sql = f"""
        SELECT p.product_key, p.name, p.brand, p.ean, p.image_url, p.net_content_raw,
               p.grammage_base, p.grammage_base_unit, p.category_slug,
               o.price, o.list_price, o.in_offer, o.best_card_price, o.unit_price_calc,
               o.ppum, o.ppum_unit, o.captured_at
        FROM products p
        JOIN observations o ON o.product_key = p.product_key
        JOIN runs r ON r.run_id = o.run_id
        WHERE r.run_id = (SELECT run_id FROM runs WHERE status IN ('ok','partial')
                          ORDER BY started_at DESC LIMIT 1)
          AND {' AND '.join(where)}
        ORDER BY o.in_offer DESC, p.name
        LIMIT ? OFFSET ?"""
    rows = [dict(r) for r in con.execute(sql, params + [limit, offset])]
    con.close()
    return rows


def product_detail(slug: str, product_key: str) -> dict:
    con = _open(slug)
    p = con.execute("SELECT * FROM products WHERE product_key=?", (product_key,)).fetchone()
    if not p:
        con.close()
        return {}
    history = [dict(r) for r in con.execute("""
        SELECT r.started_at, o.price, o.list_price, o.best_card_price, o.in_offer,
               o.unit_price_calc, o.net_content_raw, o.grammage_base, o.available
        FROM observations o JOIN runs r ON r.run_id = o.run_id
        WHERE o.product_key = ? ORDER BY r.started_at""", (product_key,))]
    prices = [h["price"] for h in history if h["price"]]
    stats = {
        "min": min(prices) if prices else None,
        "max": max(prices) if prices else None,
        "n_obs": len(history),
        "current": prices[-1] if prices else None,
    }
    # shrinkflation: did grammage_base ever drop?
    grams = [h["grammage_base"] for h in history if h["grammage_base"]]
    stats["shrinkflation"] = bool(grams and min(grams) < max(grams))
    # fake discount: an "offer" whose price >= median of recent non-offer prices
    con.close()
    return {"product": dict(p), "history": history, "stats": stats}


# -- comparador (cross-store, by EAN) ------------------------------------
def compare_by_ean(min_stores: int = 2, limit: int = 100,
                   sort: str = "gap_pct") -> list[dict]:
    stores = available_stores()
    by_ean: dict[str, dict] = {}
    name_for: dict[str, str] = {}
    img_for: dict[str, str] = {}
    for s in stores:
        con = _open(s["slug"])
        rows = con.execute("""
            SELECT p.ean, p.name, p.image_url, o.price
            FROM products p JOIN observations o ON o.product_key = p.product_key
            WHERE o.run_id = (SELECT run_id FROM runs WHERE status IN ('ok','partial')
                              ORDER BY started_at DESC LIMIT 1)
              AND p.ean IS NOT NULL AND p.ean <> '' AND o.price IS NOT NULL""")
        for r in rows:
            ean = r["ean"]
            by_ean.setdefault(ean, {})[s["slug"]] = r["price"]
            name_for.setdefault(ean, r["name"])
            if r["image_url"]:
                img_for.setdefault(ean, r["image_url"])
        con.close()

    out = []
    for ean, prices in by_ean.items():
        if len(prices) < min_stores:
            continue
        lo = min(prices.values()); hi = max(prices.values())
        if lo <= 0:
            continue
        out.append({
            "ean": ean, "name": name_for.get(ean, ean),
            "image_url": img_for.get(ean),
            "prices": prices,
            "cheapest_store": min(prices, key=prices.get),
            "dearest_store": max(prices, key=prices.get),
            "min": lo, "max": hi, "gap_abs": hi - lo,
            "gap_pct": round((hi - lo) / lo * 100, 1),
            "n_stores": len(prices),
        })
    key = {"gap_pct": "gap_pct", "gap_abs": "gap_abs"}.get(sort, "gap_pct")
    out.sort(key=lambda r: r[key], reverse=True)
    return out[:limit]


# -- ofertas / fake-discount radar (single store) ------------------------
def export_store_csv(slug: str) -> str:
    """Latest-run products + observation, flat, for R/Python."""
    con = _open(slug)
    rows = con.execute("""
        SELECT p.product_key, p.ean, p.sku, p.name, p.brand, p.category_path,
               p.net_content_raw, p.grammage_base, p.grammage_base_unit,
               o.price, o.list_price, o.price_no_disc, o.in_offer, o.best_card_price,
               o.ppum, o.ppum_unit, o.unit_price_calc, o.available, o.captured_at,
               r.location_label, r.scraper_version
        FROM products p
        JOIN observations o ON o.product_key = p.product_key
        JOIN runs r ON r.run_id = o.run_id
        WHERE o.run_id = (SELECT run_id FROM runs WHERE status IN ('ok','partial')
                          ORDER BY started_at DESC LIMIT 1)
        ORDER BY p.category_path, p.name""").fetchall()
    con.close()
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=rows[0].keys())
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
    return buf.getvalue()


def export_comparador_csv() -> str:
    rows = compare_by_ean(min_stores=2, limit=100000)
    buf = io.StringIO()
    stores = [s["slug"] for s in available_stores()]
    fields = ["ean", "name", "min", "max", "gap_abs", "gap_pct",
              "cheapest_store", "dearest_store"] + [f"price_{s}" for s in stores]
    w = csv.DictWriter(buf, fieldnames=fields)
    w.writeheader()
    for r in rows:
        row = {k: r.get(k) for k in fields if not k.startswith("price_")}
        for s in stores:
            row[f"price_{s}"] = r["prices"].get(s)
        w.writerow(row)
    return buf.getvalue()


def make_snapshot(slug: str) -> dict:
    """Copy a store's live DB to an immutable dated snapshot artifact."""
    src = config.db_path(slug)
    if not src.exists():
        raise FileNotFoundError(src)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    dst = config.SNAPSHOT_DIR / f"{slug}_{stamp}.sqlite"
    # use sqlite backup API so an in-flight WAL is consistent
    s = sqlite3.connect(src)
    d = sqlite3.connect(dst)
    with d:
        s.backup(d)
    s.close(); d.close()
    return {"snapshot": str(dst.name), "bytes": dst.stat().st_size}


def list_snapshots() -> list[dict]:
    out = []
    for p in sorted(config.SNAPSHOT_DIR.glob("*.sqlite"), reverse=True):
        out.append({"name": p.name, "bytes": p.stat().st_size,
                    "mtime": datetime.fromtimestamp(p.stat().st_mtime).isoformat()[:16]})
    return out


def offers(slug: str, limit: int = 60) -> list[dict]:
    con = _open(slug)
    rows = [dict(r) for r in con.execute("""
        SELECT p.name, p.brand, p.ean, p.image_url,
               o.price, o.list_price, o.saving_text, o.unit_price_calc, o.captured_at
        FROM products p JOIN observations o ON o.product_key = p.product_key
        WHERE o.run_id = (SELECT run_id FROM runs WHERE status IN ('ok','partial')
                          ORDER BY started_at DESC LIMIT 1)
          AND o.in_offer = 1 AND o.list_price > o.price
        ORDER BY (CAST(o.list_price - o.price AS REAL) / o.list_price) DESC
        LIMIT ?""", (limit,))]
    for r in rows:
        if r["list_price"]:
            r["discount_pct"] = round((r["list_price"] - r["price"]) / r["list_price"] * 100, 1)
    con.close()
    return rows
