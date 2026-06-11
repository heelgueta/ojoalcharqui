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


# "Latest run" = the run the most products were actually last seen in, derived
# from products.last_seen_run rather than the runs table. This is robust to
# phantom runs (a scrape that started then died before writing anything, which a
# reconcile may even stamp with a fake n_products) — those have no products
# pointing at them, so they can never shadow the real latest scrape.
_LATEST_RUN = ("(SELECT last_seen_run FROM products WHERE last_seen_run IS NOT NULL "
               "GROUP BY last_seen_run ORDER BY COUNT(*) DESC LIMIT 1)")

# Current state of every in-catalog product under delta storage: a product is
# "current" if it was seen in the latest run (products.last_seen_run), and its
# current price is its most recent observation (which may have been written in
# an earlier run and merely re-confirmed since). Read queries JOIN through this.
_CURRENT_JOIN = f"""
    FROM products p
    JOIN observations o ON o.obs_id = (
        SELECT obs_id FROM observations ox WHERE ox.product_key = p.product_key
        ORDER BY captured_at DESC, obs_id DESC LIMIT 1)
    WHERE p.last_seen_run = {_LATEST_RUN}
"""


def product_url(store: str, raw_json: str | dict | None) -> str | None:
    """Best-effort link to the product's original page on the store site, rebuilt
    from the slug/url we stored in raw_json. Verified patterns per store."""
    if not raw_json:
        return None
    raw = raw_json if isinstance(raw_json, dict) else None
    if raw is None:
        try:
            import json as _json
            raw = _json.loads(raw_json)
        except Exception:
            return None
    try:
        if store == "jumbo":
            lt = raw.get("linkText")
            return f"https://www.jumbo.cl/{lt}/p" if lt else None
        if store == "lider":
            cu = raw.get("canonicalUrl")
            return f"https://www.lider.cl{cu}" if cu else None
        if store == "unimarc":
            sl = (raw.get("item") or {}).get("slug")
            return f"https://www.unimarc.cl{sl}" if sl else None
        if store == "alvi":
            sl = (raw.get("item") or {}).get("slug")
            return f"https://www.alvi.cl{sl}" if sl else None
        if store == "acuenta":
            sl = raw.get("slug")
            return f"https://www.acuenta.cl/p/{sl}" if sl else None
    except Exception:
        return None
    return None


def reconcile_orphans(active_slugs: set[str] | None = None) -> int:
    """Heal runs left as 'running' by a crashed/killed process. Any such run that
    isn't currently live (per the engine) is downgraded to 'partial' so its data
    becomes visible to the app. Returns how many were fixed."""
    active_slugs = active_slugs or set()
    fixed = 0
    for path in config.DATA_DIR.glob("*.sqlite"):
        slug = path.stem
        if slug.startswith("_") or slug in active_slugs:
            continue
        try:
            con = sqlite3.connect(path)
            cur = con.execute(
                """UPDATE runs SET status='partial',
                       finished_at=COALESCE(finished_at, started_at),
                       notes=COALESCE(NULLIF(notes,''), 'interrupted; reconciled'),
                       n_products=(SELECT COUNT(*) FROM products)
                   WHERE status='running'""")
            fixed += cur.rowcount or 0
            con.commit()
            con.close()
        except Exception:
            continue
    return fixed


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
_SORT_SQL = {
    "relevancia": "o.in_offer DESC, p.name",
    "precio_asc": "o.price ASC, p.name",
    "precio_desc": "o.price DESC, p.name",
    "nombre": "p.name",
}


def search_products(slug: str, q: str = "", limit: int = 60, offset: int = 0,
                    only_offers: bool = False, sort: str = "relevancia") -> list[dict]:
    con = _open(slug)
    where, params = ["1=1"], []
    if q:
        where.append("(p.name LIKE ? OR p.brand LIKE ? OR p.ean = ?)")
        params += [f"%{q}%", f"%{q}%", q]
    if only_offers:
        where.append("o.in_offer = 1")
    order = _SORT_SQL.get(sort, _SORT_SQL["relevancia"])
    sql = f"""
        SELECT p.product_key, p.name, p.brand, p.ean, p.image_url, p.net_content_raw,
               p.grammage_base, p.grammage_base_unit, p.category_slug,
               o.price, o.list_price, o.in_offer, o.best_card_price, o.unit_price_calc,
               o.ppum, o.ppum_unit, o.captured_at
        {_CURRENT_JOIN}
          AND {' AND '.join(where)}
        ORDER BY {order}
        LIMIT ? OFFSET ?"""
    rows = [dict(r) for r in con.execute(sql, params + [limit, offset])]
    con.close()
    return rows


def search_all_products(q: str = "", per_store: int = 40, total: int = 120,
                        only_offers: bool = False, sort: str = "relevancia") -> list[dict]:
    """Search across every store at once. Each row is tagged with its store so
    the Explorador can show all chains together (the default view)."""
    out = []
    for s in available_stores():
        if not s["n_products"]:
            continue
        for r in search_products(s["slug"], q, limit=per_store, only_offers=only_offers, sort=sort):
            r["store"] = s["slug"]
            r["store_name"] = s["name"]
            out.append(r)
    if sort == "precio_asc":
        out.sort(key=lambda r: (r.get("price") is None, r.get("price") or 0))
    elif sort == "precio_desc":
        out.sort(key=lambda r: (r.get("price") or 0), reverse=True)
    elif sort == "nombre":
        out.sort(key=lambda r: (r.get("name") or "").lower())
    else:
        out.sort(key=lambda r: (0 if r.get("in_offer") else 1, (r.get("name") or "").lower()))
    return out[:total]


def product_detail(slug: str, product_key: str) -> dict:
    con = _open(slug)
    p = con.execute("SELECT * FROM products WHERE product_key=?", (product_key,)).fetchone()
    if not p:
        con.close()
        return {}
    history = [dict(r) for r in con.execute("""
        SELECT r.started_at, r.location_label, o.price, o.list_price, o.best_card_price,
               o.in_offer, o.unit_price_calc, o.net_content_raw, o.grammage_base, o.available
        FROM observations o JOIN runs r ON r.run_id = o.run_id
        WHERE o.product_key = ? ORDER BY r.started_at""", (product_key,))]
    prices = [h["price"] for h in history if h["price"]]
    stats = {
        "min": min(prices) if prices else None,
        "max": max(prices) if prices else None,
        "n_obs": len(history),
        "current": prices[-1] if prices else None,
        "mean": round(sum(prices) / len(prices)) if prices else None,
    }
    # shrinkflation: did grammage_base ever drop?
    grams = [h["grammage_base"] for h in history if h["grammage_base"]]
    stats["shrinkflation"] = bool(grams and min(grams) < max(grams))

    # latest card/club prices for this product
    cards = [dict(r) for r in con.execute("""
        SELECT cp.payment_method, cp.promo_name, cp.price, cp.ppum, cp.saving
        FROM card_prices cp
        WHERE cp.obs_id = (SELECT obs_id FROM observations WHERE product_key=?
                           ORDER BY captured_at DESC LIMIT 1)
        ORDER BY cp.price""", (product_key,))]

    # same product in other stores (by EAN) — cross-store mini-compare
    cross = []
    pe = p["ean"]
    if pe:
        for s in available_stores():
            if s["slug"] == slug:
                continue
            try:
                oc = _open(s["slug"])
                row = oc.execute("""
                    SELECT p.product_key, p.name, o.price
                    FROM products p JOIN observations o ON o.product_key=p.product_key
                    WHERE o.run_id=(SELECT run_id FROM runs WHERE status IN ('ok','partial')
                                    ORDER BY started_at DESC LIMIT 1)
                      AND p.ean=? AND o.price IS NOT NULL
                    ORDER BY o.price LIMIT 1""", (pe,)).fetchone()
                oc.close()
                if row:
                    cross.append({"store": s["slug"], "store_name": s["name"],
                                  "product_key": row["product_key"],
                                  "name": row["name"], "price": row["price"]})
            except Exception:
                continue
    con.close()
    last = history[-1] if history else {}
    return {"product": dict(p), "history": history, "stats": stats,
            "cards": cards, "cross": cross,
            "store_url": product_url(slug, p["raw_json"]),
            "scrape_date": last.get("started_at"),
            "scrape_location": last.get("location_label")}


def _grammage_mismatch(chosen, tol: float = 1.12) -> bool:
    """True if the chosen per-store products clearly differ in net content
    (different base unit, or size ratio beyond `tol`). Only judges when at least
    two of them actually carry a grammage; otherwise returns False (can't tell)."""
    grams = [(c.get("gram"), c.get("gunit")) for c in chosen if c.get("gram")]
    if len(grams) < 2:
        return False
    units = {u for _, u in grams if u}
    if len(units) > 1:                 # ml vs g vs un — different product
        return True
    vals = [g for g, _ in grams]
    return (max(vals) / min(vals)) > tol if min(vals) > 0 else False


def _name_tokens(name: str) -> set[str]:
    """Cheap tokenizer for the name-agreement guard (no accents, no grammage)."""
    import re
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFD", (name or "").lower())
                if unicodedata.category(c) != "Mn")
    n = re.sub(r"\b\d+([.,]\d+)?\s*(kg|g|gr|grs|mg|l|lt|ml|cc|un|u|pack)\b", " ", n)
    stop = {"de", "la", "el", "con", "sin", "y", "pack", "sabor", "un"}
    return {t for t in re.findall(r"[a-z0-9]+", n) if len(t) > 1 and t not in stop}


# -- comparador (cross-store, by EAN) ------------------------------------
def compare_by_ean(min_stores: int = 2, limit: int = 100, sort: str = "gap_pct",
                   include_suspect: bool = False) -> list[dict]:
    """Same product (by EAN) across stores. Robust to two data hazards:
    * intra-store EAN collisions (a wrong EAN on a different product) — we keep,
      per store, the candidate whose name best agrees with the other stores.
    * cross-store name disagreement — rows where the matched products clearly
      aren't the same thing (bad source EAN) are flagged suspect and hidden by
      default, so the headline gaps are real, not data errors.
    """
    stores = available_stores()
    # ean -> store -> list of {price, name, image}
    cand: dict[str, dict[str, list]] = {}
    for s in stores:
        con = _open(s["slug"])
        rows = con.execute(f"""
            SELECT p.ean, p.product_key, p.name, p.image_url,
                   p.grammage_base, p.grammage_base_unit, o.price, o.best_card_price
            {_CURRENT_JOIN}
              AND p.ean IS NOT NULL AND p.ean <> '' AND o.price IS NOT NULL AND o.price > 0""")
        for r in rows:
            cand.setdefault(r["ean"], {}).setdefault(s["slug"], []).append(
                {"price": r["price"], "name": r["name"], "image": r["image_url"],
                 "product_key": r["product_key"], "gram": r["grammage_base"],
                 "gunit": r["grammage_base_unit"], "card": r["best_card_price"]})
        con.close()

    out = []
    for ean, per_store in cand.items():
        if len(per_store) < min_stores:
            continue
        # reference token set = most frequent tokens across all candidates
        from collections import Counter
        tok_counter: Counter = Counter()
        for lst in per_store.values():
            for c in lst:
                tok_counter.update(_name_tokens(c["name"]))
        ref = {t for t, n in tok_counter.items() if n >= 1}

        chosen: dict[str, dict] = {}
        for store, lst in per_store.items():
            # pick the candidate whose name best agrees with the reference
            best = max(lst, key=lambda c: len(_name_tokens(c["name"]) & ref))
            chosen[store] = best

        prices = {st: c["price"] for st, c in chosen.items()}
        product_keys = {st: c["product_key"] for st, c in chosen.items()}
        card_prices = {st: c["card"] for st, c in chosen.items() if c.get("card")}
        lo, hi = min(prices.values()), max(prices.values())
        cheapest = min(prices, key=prices.get)
        dearest = max(prices, key=prices.get)

        # name-agreement guard between the two extreme stores
        ta = _name_tokens(chosen[cheapest]["name"])
        tb = _name_tokens(chosen[dearest]["name"])
        jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0
        # grammage-agreement guard: products sharing an EAN but with clearly
        # different net content are a mislabeled EAN, not the same product
        # (e.g. Acuenta 500 ml vs Unimarc 750 g) — exclude, the "gap" is bogus.
        gram_mismatch = _grammage_mismatch(chosen.values())
        suspect = jac < 0.34 or gram_mismatch
        if suspect and not include_suspect:
            continue

        img = next((c["image"] for c in chosen.values() if c["image"]), None)
        out.append({
            "ean": ean, "name": chosen[cheapest]["name"], "image_url": img,
            "prices": prices, "product_keys": product_keys, "card_prices": card_prices,
            "method": "ean",
            "cheapest_store": cheapest, "dearest_store": dearest,
            "min": lo, "max": hi, "gap_abs": hi - lo,
            "gap_pct": round((hi - lo) / lo * 100, 1),
            "n_stores": len(prices), "suspect": suspect, "name_agree": round(jac, 2),
            "gram_mismatch": gram_mismatch,
        })
    key = {"gap_pct": "gap_pct", "gap_abs": "gap_abs"}.get(sort, "gap_pct")
    out.sort(key=lambda r: r[key], reverse=True)
    return out[:limit]


# -- variación: largest price changes over time --------------------------
def price_changes(store: str = "all", sort: str = "pct", limit: int = 100,
                  direction: str = "all") -> list[dict]:
    """Products whose price moved the most across their observation history
    (first recorded state -> latest state). Needs >= 2 observations, i.e. the
    longitudinal series — so it fills in as repeat scrapes accumulate."""
    stores = ([s for s in available_stores() if s["n_products"]]
              if store == "all" else
              [s for s in available_stores() if s["slug"] == store])
    out = []
    for s in stores:
        con = _open(s["slug"])
        rows = con.execute("""
            SELECT p.product_key, p.name, p.brand, p.image_url, p.ean,
                   fo.price AS first_price, fo.captured_at AS first_at,
                   lo.price AS last_price,  lo.last_seen_at AS last_at,
                   (SELECT COUNT(*) FROM observations WHERE product_key = p.product_key) AS n_points
            FROM products p
            JOIN observations fo ON fo.obs_id = (
                SELECT obs_id FROM observations WHERE product_key = p.product_key
                ORDER BY captured_at ASC, obs_id ASC LIMIT 1)
            JOIN observations lo ON lo.obs_id = (
                SELECT obs_id FROM observations WHERE product_key = p.product_key
                ORDER BY captured_at DESC, obs_id DESC LIMIT 1)
            WHERE p.last_seen_run = """ + _LATEST_RUN + """
              AND (SELECT COUNT(*) FROM observations WHERE product_key = p.product_key) >= 2
              AND fo.price IS NOT NULL AND lo.price IS NOT NULL AND fo.price <> lo.price
        """).fetchall()
        for r in rows:
            fp, lp = r["first_price"], r["last_price"]
            ch_abs = lp - fp
            ch_pct = round(ch_abs / fp * 100, 1) if fp else 0
            d = dict(r)
            d.update({"store": s["slug"], "store_name": s["name"],
                      "change_abs": ch_abs, "change_pct": ch_pct,
                      "direction": "up" if ch_abs > 0 else "down"})
            out.append(d)
        con.close()
    if direction in ("up", "down"):
        out = [r for r in out if r["direction"] == direction]
    key = "change_abs" if sort == "abs" else "change_pct"
    out.sort(key=lambda r: abs(r[key]), reverse=True)
    return out[:limit]


# -- ofertas / fake-discount radar (single store) ------------------------
def export_store_csv(slug: str) -> str:
    """Latest-run products + observation, flat, for R/Python."""
    con = _open(slug)
    rows = con.execute(f"""
        SELECT p.product_key, p.ean, p.sku, p.name, p.brand, p.category_path,
               p.net_content_raw, p.grammage_base, p.grammage_base_unit,
               o.price, o.list_price, o.price_no_disc, o.in_offer, o.best_card_price,
               o.ppum, o.ppum_unit, o.unit_price_calc, o.available, o.captured_at,
               o.last_seen_at, o.n_seen
        {_CURRENT_JOIN}
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
    rows = [dict(r) for r in con.execute(f"""
        SELECT p.name, p.brand, p.ean, p.image_url, p.product_key,
               o.price, o.list_price, o.saving_text, o.unit_price_calc, o.captured_at
        {_CURRENT_JOIN}
          AND o.in_offer = 1 AND o.list_price > o.price
        ORDER BY (CAST(o.list_price - o.price AS REAL) / o.list_price) DESC
        LIMIT ?""", (limit,))]
    for r in rows:
        if r["list_price"]:
            r["discount_pct"] = round((r["list_price"] - r["price"]) / r["list_price"] * 100, 1)
    con.close()
    return rows
