"""Cross-store product matching — the Emparejador.

Two tiers:
  * EAN exact  -> auto-confirmed groups (free, reliable). Acuenta & Unimarc
    expose clean EAN-13; any products sharing an EAN are the same product.
  * Fuzzy      -> candidate pairs for human review, blocked on
    (brand, grammage) and scored by name-token Jaccard. Jumbo (no EAN) and the
    EAN-less tail need this. Humans confirm/reject in the UI; confirmations
    become a labeled dataset we can later train on.

Everything lands in a central catalog DB (data/_catalog.sqlite). Store DBs are
read-only here; we snapshot each store's latest run.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from itertools import combinations
from pathlib import Path

from . import config, queries

CATALOG_DB = config.DATA_DIR / "_catalog.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshot (
    store        TEXT, product_key TEXT, ean TEXT, name TEXT, brand TEXT,
    grammage_base REAL, grammage_base_unit TEXT, price INTEGER, image_url TEXT,
    norm_brand TEXT, tokens TEXT,
    PRIMARY KEY(store, product_key)
);
CREATE INDEX IF NOT EXISTS idx_snap_ean ON snapshot(ean);
CREATE INDEX IF NOT EXISTS idx_snap_block ON snapshot(norm_brand, grammage_base);

CREATE TABLE IF NOT EXISTS groups (
    group_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    label      TEXT,
    method     TEXT,            -- ean | manual
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS group_members (
    group_id    INTEGER, store TEXT, product_key TEXT,
    UNIQUE(store, product_key)
);

CREATE TABLE IF NOT EXISTS candidates (
    cand_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    store_a TEXT, key_a TEXT, store_b TEXT, key_b TEXT,
    score   REAL, reason TEXT,
    status  TEXT DEFAULT 'pending',   -- pending | confirmed | rejected
    UNIQUE(store_a, key_a, store_b, key_b)
);
"""

_STOP = {"de", "la", "el", "los", "las", "con", "sin", "y", "para", "x", "un",
         "una", "sabor", "pack", "gr", "kg", "ml", "lt", "l", "g", "cc", "un."}
_UNIT_TOK = re.compile(r"\b\d+([.,]\d+)?\s*(kg|kgs|g|gr|grs|mg|l|lt|lts|ml|cc|un|u|pack)\b", re.I)


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_brand(b: str | None) -> str:
    if not b:
        return ""
    return re.sub(r"[^a-z0-9]", "", _strip_accents(b).lower())


def tokenize(name: str) -> set[str]:
    n = _strip_accents(name or "").lower()
    n = _UNIT_TOK.sub(" ", n)
    toks = re.findall(r"[a-z0-9]+", n)
    return {t for t in toks if t not in _STOP and len(t) > 1}


def _open_catalog() -> sqlite3.Connection:
    con = sqlite3.connect(CATALOG_DB)
    con.row_factory = sqlite3.Row
    con.executescript(_SCHEMA)
    return con


def rebuild_snapshot(con: sqlite3.Connection) -> int:
    """Pull each store's latest-run products into the central snapshot table."""
    con.execute("DELETE FROM snapshot")
    n = 0
    for s in queries.available_stores():
        rows = queries.search_products(s["slug"], q="", limit=100000)
        for r in rows:
            con.execute(
                """INSERT OR REPLACE INTO snapshot(store, product_key, ean, name, brand,
                       grammage_base, grammage_base_unit, price, image_url, norm_brand, tokens)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (s["slug"], r["product_key"], (r["ean"] or None), r["name"], r["brand"],
                 r["grammage_base"], r["grammage_base_unit"], r["price"], r["image_url"],
                 norm_brand(r["brand"]), " ".join(sorted(tokenize(r["name"])))))
            n += 1
    con.commit()
    return n


def build_ean_groups(con: sqlite3.Connection) -> int:
    """Group products that share an EAN across >= 2 stores. Auto-confirmed."""
    con.execute("DELETE FROM group_members")
    con.execute("DELETE FROM groups WHERE method='ean'")
    rows = con.execute(
        """SELECT ean, store, product_key, name FROM snapshot
           WHERE ean IS NOT NULL AND ean <> ''""").fetchall()
    by_ean: dict[str, list] = {}
    for r in rows:
        by_ean.setdefault(r["ean"], []).append(r)
    groups = 0
    for ean, members in by_ean.items():
        stores = {m["store"] for m in members}
        if len(stores) < 2:
            continue
        cur = con.execute("INSERT INTO groups(label, method) VALUES(?, 'ean')",
                          (members[0]["name"][:80],))
        gid = cur.lastrowid
        for m in members:
            con.execute("INSERT OR IGNORE INTO group_members(group_id, store, product_key) VALUES(?,?,?)",
                        (gid, m["store"], m["product_key"]))
        groups += 1
    con.commit()
    return groups


AUTO_SCORE = 0.80       # >= this, same brand+grammage -> auto-confirmed group
AUTO_MAX_RATIO = 3.0    # but not if prices differ >3x (likely a variant mismatch,
                        # e.g. "Gran Reserva" vs base wine sharing a short name)


def build_fuzzy_candidates(con: sqlite3.Connection, min_score: float = 0.45,
                           max_pairs: int = 8000) -> dict:
    """Block on (norm_brand, grammage_base); within a block, score cross-store
    pairs by token Jaccard. Very high scores become auto-confirmed groups (so
    Jumbo/Líder, which lack EAN, still enter the Comparador); the rest queue for
    human review. Returns {queued, auto}."""
    con.execute("DELETE FROM candidates WHERE status='pending'")
    con.execute("DELETE FROM groups WHERE method='auto'")
    # keep manually reviewed verdicts; rebuild auto links each time
    reviewed = {(r["store_a"], r["key_a"], r["store_b"], r["key_b"]): r["status"]
                for r in con.execute("SELECT * FROM candidates WHERE status IN ('confirmed','rejected')")}
    linked = {(r["store"], r["product_key"]) for r in
              con.execute("""SELECT gm.store, gm.product_key FROM group_members gm
                             JOIN groups g ON g.group_id=gm.group_id WHERE g.method='ean'""")}
    rows = con.execute(
        """SELECT store, product_key, name, brand, norm_brand, grammage_base,
                  grammage_base_unit, tokens, price, image_url
           FROM snapshot WHERE norm_brand <> '' AND grammage_base IS NOT NULL""").fetchall()
    blocks: dict[tuple, list] = {}
    for r in rows:
        blocks.setdefault((r["norm_brand"], round(r["grammage_base"], 2)), []).append(r)
    queued = auto = 0
    for block in blocks.values():
        if len(block) < 2 or len(block) > 120:
            continue
        for a, b in combinations(block, 2):
            if a["store"] == b["store"]:
                continue
            if (a["store"], a["product_key"]) in linked or (b["store"], b["product_key"]) in linked:
                continue
            ta, tb = set(a["tokens"].split()), set(b["tokens"].split())
            if not ta or not tb:
                continue
            jac = len(ta & tb) / len(ta | tb)
            if jac < min_score:
                continue
            (sa0, sa1), (sb0, sb1) = sorted([(a["store"], a["product_key"]),
                                             (b["store"], b["product_key"])])
            verdict = reviewed.get((sa0, sa1, sb0, sb1))
            if verdict == "rejected":
                continue
            # price-ratio sanity: an extreme gap on a "match" is usually a
            # variant collision, not a real price difference -> send to review.
            pa, pb = a["price"], b["price"]
            ratio = (max(pa, pb) / min(pa, pb)) if (pa and pb and min(pa, pb) > 0) else 1.0
            if verdict == "confirmed" or (jac >= AUTO_SCORE and ratio <= AUTO_MAX_RATIO):
                _link_group(con, "auto" if verdict != "confirmed" else "manual",
                            a["name"], [(sa0, sa1), (sb0, sb1)])
                auto += 1
                continue
            con.execute(
                """INSERT OR IGNORE INTO candidates(store_a, key_a, store_b, key_b, score, reason)
                   VALUES(?,?,?,?,?,?)""",
                (sa0, sa1, sb0, sb1, round(jac, 3), f"marca+gramaje, jaccard={jac:.2f}"))
            queued += 1
            if queued >= max_pairs:
                con.commit()
                return {"queued": queued, "auto": auto}
    con.commit()
    return {"queued": queued, "auto": auto}


def _link_group(con, method: str, label: str, members: list[tuple]):
    cur = con.execute("INSERT INTO groups(label, method) VALUES(?,?)", ((label or "")[:80], method))
    gid = cur.lastrowid
    for st, key in members:
        con.execute("INSERT OR IGNORE INTO group_members(group_id, store, product_key) VALUES(?,?,?)",
                    (gid, st, key))
    return gid


def rebuild_all() -> dict:
    con = _open_catalog()
    n = rebuild_snapshot(con)
    g = build_ean_groups(con)
    f = build_fuzzy_candidates(con)
    con.close()
    return {"snapshot": n, "ean_groups": g,
            "fuzzy_candidates": f["queued"], "auto_groups": f["auto"]}


# -- read side for the UI -------------------------------------------------
def _detail(con, store, key):
    r = con.execute("SELECT * FROM snapshot WHERE store=? AND product_key=?", (store, key)).fetchone()
    return dict(r) if r else {"store": store, "product_key": key, "name": "(no encontrado)"}


def candidate_queue(limit: int = 40, status: str = "pending") -> list[dict]:
    con = _open_catalog()
    rows = con.execute(
        "SELECT * FROM candidates WHERE status=? ORDER BY score DESC LIMIT ?",
        (status, limit)).fetchall()
    out = []
    for r in rows:
        out.append({**dict(r),
                    "a": _detail(con, r["store_a"], r["key_a"]),
                    "b": _detail(con, r["store_b"], r["key_b"])})
    con.close()
    return out


def set_candidate_status(cand_id: int, status: str):
    con = _open_catalog()
    row = con.execute("SELECT * FROM candidates WHERE cand_id=?", (cand_id,)).fetchone()
    if row and status == "confirmed":
        cur = con.execute("INSERT INTO groups(label, method) VALUES(?, 'manual')",
                          (_detail(con, row["store_a"], row["key_a"])["name"][:80],))
        gid = cur.lastrowid
        for st, key in [(row["store_a"], row["key_a"]), (row["store_b"], row["key_b"])]:
            con.execute("INSERT OR IGNORE INTO group_members(group_id, store, product_key) VALUES(?,?,?)",
                        (gid, st, key))
    con.execute("UPDATE candidates SET status=? WHERE cand_id=?", (status, cand_id))
    con.commit()
    con.close()


def compare_by_group(limit: int = 150, sort: str = "gap_pct",
                     methods: tuple = ("ean", "auto", "manual")) -> list[dict]:
    """Cross-store price comparison built from matched groups (EAN + fuzzy).
    This is the superset of the EAN-only comparador and includes Jumbo/Líder via
    auto/manual matches. One row per group with >= 2 stores."""
    if not CATALOG_DB.exists():
        return []
    con = _open_catalog()
    qmarks = ",".join("?" * len(methods))
    grows = con.execute(
        f"""SELECT g.group_id, g.method, gm.store, gm.product_key
            FROM groups g JOIN group_members gm ON gm.group_id=g.group_id
            WHERE g.method IN ({qmarks})""", methods).fetchall()
    # gather snapshot info per member
    by_group: dict[int, dict] = {}
    for r in grows:
        snap = con.execute("SELECT name, price, image_url FROM snapshot WHERE store=? AND product_key=?",
                           (r["store"], r["product_key"])).fetchone()
        if not snap or snap["price"] is None:
            continue
        g = by_group.setdefault(r["group_id"], {"method": r["method"], "prices": {},
                                                "names": {}, "product_keys": {}, "image": None})
        # keep the cheapest member per store
        if r["store"] not in g["prices"] or snap["price"] < g["prices"][r["store"]]:
            g["prices"][r["store"]] = snap["price"]
            g["names"][r["store"]] = snap["name"]
            g["product_keys"][r["store"]] = r["product_key"]
        if snap["image_url"] and not g["image"]:
            g["image"] = snap["image_url"]
    con.close()

    out = []
    for gid, g in by_group.items():
        prices = g["prices"]
        if len(prices) < 2:
            continue
        lo, hi = min(prices.values()), max(prices.values())
        if lo <= 0:
            continue
        cheapest = min(prices, key=prices.get)
        out.append({
            "group_id": gid, "method": g["method"],
            "name": g["names"][cheapest], "image_url": g["image"],
            "prices": prices, "product_keys": g["product_keys"],
            "cheapest_store": cheapest, "dearest_store": max(prices, key=prices.get),
            "min": lo, "max": hi, "gap_abs": hi - lo,
            "gap_pct": round((hi - lo) / lo * 100, 1), "n_stores": len(prices),
        })
    key = "gap_abs" if sort == "gap_abs" else "gap_pct"
    out.sort(key=lambda r: r[key], reverse=True)
    return out[:limit]


def stats() -> dict:
    if not CATALOG_DB.exists():
        return {"snapshot": 0, "ean_groups": 0, "pending": 0, "confirmed": 0, "rejected": 0}
    con = _open_catalog()
    def c(sql, *a): return con.execute(sql, a).fetchone()[0]
    out = {
        "snapshot": c("SELECT COUNT(*) FROM snapshot"),
        "ean_groups": c("SELECT COUNT(*) FROM groups WHERE method='ean'"),
        "auto_groups": c("SELECT COUNT(*) FROM groups WHERE method='auto'"),
        "manual_groups": c("SELECT COUNT(*) FROM groups WHERE method='manual'"),
        "pending": c("SELECT COUNT(*) FROM candidates WHERE status='pending'"),
        "confirmed": c("SELECT COUNT(*) FROM candidates WHERE status='confirmed'"),
        "rejected": c("SELECT COUNT(*) FROM candidates WHERE status='rejected'"),
    }
    con.close()
    return out
