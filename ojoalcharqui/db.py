"""SQLite schema and access for a single store.

Design goals
------------
* One file per store (``data/<slug>.sqlite``). Each file self-identifies via the
  ``meta`` table (store slug, platform, schema version, a per-file UUID).
* Append-only fact table ``observations`` — one row per product per run. Prices,
  availability and a grammage snapshot live here, so the full longitudinal series
  (incl. shrinkflation and fake-discount detection) is reconstructable.
* ``runs`` carries the provenance every reviewer will ask for: timestamps,
  scraper version, location/sales-channel, counts, parameters.
* Merge-friendly: ``run_id`` is a UUID and ``product_key`` is the store-native id,
  so two people's DBs for the same store union without collisions (see
  :func:`merge_from`). Concern raised by Herman: 2026 data + 2027 data must join.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import SCHEMA_VERSION

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- one row per scrape run (provenance)
CREATE TABLE IF NOT EXISTS runs (
    run_id          TEXT PRIMARY KEY,          -- uuid4
    store_slug      TEXT NOT NULL,
    started_at      TEXT NOT NULL,             -- ISO8601 UTC
    finished_at     TEXT,
    status          TEXT NOT NULL,             -- running | ok | partial | error
    scraper_version TEXT NOT NULL,
    location_label  TEXT,                      -- e.g. "Santiago Centro"
    comuna          TEXT,
    sales_channel   TEXT,
    n_categories    INTEGER DEFAULT 0,
    n_products      INTEGER DEFAULT 0,
    n_observations  INTEGER DEFAULT 0,
    n_changed       INTEGER DEFAULT 0,
    n_unchanged     INTEGER DEFAULT 0,
    n_errors        INTEGER DEFAULT 0,
    duration_s      REAL,
    params_json     TEXT,
    notes           TEXT
);

-- relatively-stable catalog dimension; "latest known" snapshot per product
CREATE TABLE IF NOT EXISTS products (
    product_key      TEXT PRIMARY KEY,         -- store-native id (itemId/sku)
    ean              TEXT,
    sku              TEXT,
    name             TEXT,
    brand            TEXT,
    brand_id         TEXT,
    description      TEXT,
    category_path    TEXT,                     -- "/Despensa/Arroz y legumbres/Arroz/"
    category_slug    TEXT,
    measurement_unit TEXT,
    net_content_raw  TEXT,                     -- "1 Kg"
    grammage_value   REAL,                     -- 1.0
    grammage_unit    TEXT,                     -- kg
    grammage_base    REAL,                     -- normalized to g / ml / un
    grammage_base_unit TEXT,                   -- g | ml | un
    pack_units       INTEGER,                  -- e.g. 6 (pack of 6)
    image_url        TEXT,
    first_seen_run   TEXT,
    last_seen_run    TEXT,
    raw_json         TEXT
);
CREATE INDEX IF NOT EXISTS idx_products_ean   ON products(ean);
CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand);

-- change-log fact table: one row per *price state* per product. A new row is
-- written only when something changed vs the previous state; an unchanged
-- re-scrape just stamps last_seen_run/last_seen_at and bumps n_seen. So the
-- price history is the sequence of rows, each valid [captured_at, last_seen_at].
CREATE TABLE IF NOT EXISTS observations (
    obs_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           TEXT NOT NULL,            -- run that first recorded this state
    product_key      TEXT NOT NULL,
    captured_at      TEXT NOT NULL,            -- when this state began
    last_seen_run    TEXT,                     -- most recent run that confirmed it
    last_seen_at     TEXT,                     -- timestamp of that confirmation
    n_seen           INTEGER DEFAULT 1,        -- how many runs saw this exact state
    available        INTEGER,                  -- 1/0
    price            INTEGER,                  -- effective price, CLP
    list_price       INTEGER,                  -- precio normal / tachado
    price_no_disc    INTEGER,                  -- priceWithoutDiscount
    in_offer         INTEGER,
    best_card_price  INTEGER,                  -- cheapest card/club price
    best_card_name   TEXT,
    ppum             INTEGER,                  -- store's price-per-unit-measure
    ppum_unit        TEXT,                     -- Kg / L / un
    unit_price_calc  REAL,                     -- our price / grammage_base
    saving_text      TEXT,
    promo_text       TEXT,                     -- unstructured promo blurb
    net_content_raw  TEXT,                     -- grammage snapshot (shrinkflation)
    grammage_base    REAL,
    raw_json         TEXT,
    UNIQUE(run_id, product_key)
);
CREATE INDEX IF NOT EXISTS idx_obs_product ON observations(product_key);
CREATE INDEX IF NOT EXISTS idx_obs_run     ON observations(run_id);
CREATE INDEX IF NOT EXISTS idx_obs_latest  ON observations(product_key, captured_at);

-- card / club / payment-method prices, one row per offer per observation
CREATE TABLE IF NOT EXISTS card_prices (
    obs_id          INTEGER NOT NULL,
    run_id          TEXT NOT NULL,
    product_key     TEXT NOT NULL,
    payment_method  TEXT,
    promo_name      TEXT,
    price           INTEGER,
    ppum            TEXT,
    saving          TEXT
);
CREATE INDEX IF NOT EXISTS idx_card_obs ON card_prices(obs_id);

-- taxonomy snapshot per run (category drift is data too)
CREATE TABLE IF NOT EXISTS categories (
    run_id        TEXT NOT NULL,
    category_id   TEXT,
    name          TEXT,
    slug          TEXT,
    parent_slug   TEXT,
    level         INTEGER,
    n_products    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_cat_run ON categories(run_id);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


class StoreDB:
    """Connection wrapper for one store's SQLite file."""

    def __init__(self, path: str | Path, store_slug: str, store_name: str = "",
                 platform: str = ""):
        self.path = Path(path)
        self.store_slug = store_slug
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        # Backfill meta whenever store_slug is missing — not just on a brand-new
        # file. A first run that crashed between table-creation and the meta
        # commit would otherwise leave the DB permanently identity-less (the file
        # exists, so the old `first_time` guard never re-wrote it). Bit Líder.
        have_slug = self.conn.execute(
            "SELECT value FROM meta WHERE key='store_slug'").fetchone()
        if not have_slug:
            self._init_meta(store_slug, store_name, platform)
        self.conn.commit()

    def _migrate(self):
        """Additive migrations for DBs created under an older schema (v1 -> v2:
        delta-storage columns). SQLite ADD COLUMN is cheap and idempotent here."""
        def cols(table):
            return {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
        obs = cols("observations")
        for name, ddl in [("last_seen_run", "TEXT"), ("last_seen_at", "TEXT"),
                          ("n_seen", "INTEGER DEFAULT 1")]:
            if name not in obs:
                self.conn.execute(f"ALTER TABLE observations ADD COLUMN {name} {ddl}")
        runs = cols("runs")
        for name in ("n_changed", "n_unchanged"):
            if name not in runs:
                self.conn.execute(f"ALTER TABLE runs ADD COLUMN {name} INTEGER DEFAULT 0")
        # backfill last_seen for pre-existing rows so reads have a value
        self.conn.execute("""UPDATE observations
                             SET last_seen_run = COALESCE(last_seen_run, run_id),
                                 last_seen_at  = COALESCE(last_seen_at, captured_at)
                             WHERE last_seen_run IS NULL""")
        self.conn.commit()

    def _init_meta(self, slug, name, platform):
        meta = {
            "store_slug": slug,
            "store_name": name,
            "platform": platform,
            "schema_version": str(SCHEMA_VERSION),
            "db_uuid": str(uuid.uuid4()),
            "created_at": utcnow(),
        }
        self.conn.executemany("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)",
                              list(meta.items()))

    # -- meta -------------------------------------------------------------
    def get_meta(self, key: str, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str):
        self.conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, value))
        self.conn.commit()

    # -- runs -------------------------------------------------------------
    def start_run(self, scraper_version: str, location_label="", comuna="",
                  sales_channel="", params: dict | None = None) -> str:
        run_id = new_run_id()
        self.conn.execute(
            """INSERT INTO runs(run_id, store_slug, started_at, status, scraper_version,
                                location_label, comuna, sales_channel, params_json)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (run_id, self.store_slug, utcnow(), "running", scraper_version,
             location_label, comuna, sales_channel, json.dumps(params or {})),
        )
        self.conn.commit()
        return run_id

    def finish_run(self, run_id: str, status: str, **counts):
        started = self.conn.execute("SELECT started_at FROM runs WHERE run_id=?",
                                    (run_id,)).fetchone()["started_at"]
        dur = (datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()
        # delta-aware counts (deduped; engine yield counters overcount recurrences):
        #   n_changed   = new state rows written this run
        #   n_unchanged = products re-confirmed this run (last_seen_run = run, but
        #                 their state row belongs to an earlier run)
        #   n_products  = total distinct products seen this run = changed + unchanged
        n_changed = self.conn.execute(
            "SELECT COUNT(*) FROM observations WHERE run_id=?", (run_id,)).fetchone()[0]
        n_unchanged = self.conn.execute(
            "SELECT COUNT(*) FROM observations WHERE last_seen_run=? AND run_id<>?",
            (run_id, run_id)).fetchone()[0]
        n_prod = n_changed + n_unchanged
        self.conn.execute(
            """UPDATE runs SET finished_at=?, status=?, duration_s=?,
                   n_categories=?, n_products=?, n_observations=?,
                   n_changed=?, n_unchanged=?, n_errors=?, notes=?
               WHERE run_id=?""",
            (utcnow(), status, dur, counts.get("n_categories", 0), n_prod, n_changed,
             n_changed, n_unchanged, counts.get("n_errors", 0), counts.get("notes", ""), run_id),
        )
        self.conn.commit()

    # -- writes -----------------------------------------------------------
    def upsert_product(self, p: dict, run_id: str):
        existing = self.conn.execute(
            "SELECT first_seen_run FROM products WHERE product_key=?",
            (p["product_key"],)).fetchone()
        first_seen = existing["first_seen_run"] if existing else run_id
        self.conn.execute(
            """INSERT INTO products(product_key, ean, sku, name, brand, brand_id,
                   description, category_path, category_slug, measurement_unit,
                   net_content_raw, grammage_value, grammage_unit, grammage_base,
                   grammage_base_unit, pack_units, image_url, first_seen_run,
                   last_seen_run, raw_json)
               VALUES(:product_key,:ean,:sku,:name,:brand,:brand_id,:description,
                   :category_path,:category_slug,:measurement_unit,:net_content_raw,
                   :grammage_value,:grammage_unit,:grammage_base,:grammage_base_unit,
                   :pack_units,:image_url,:first_seen,:last_seen,:raw_json)
               ON CONFLICT(product_key) DO UPDATE SET
                   ean=excluded.ean, sku=excluded.sku, name=excluded.name,
                   brand=excluded.brand, brand_id=excluded.brand_id,
                   description=excluded.description, category_path=excluded.category_path,
                   category_slug=excluded.category_slug,
                   measurement_unit=excluded.measurement_unit,
                   net_content_raw=excluded.net_content_raw,
                   grammage_value=excluded.grammage_value,
                   grammage_unit=excluded.grammage_unit,
                   grammage_base=excluded.grammage_base,
                   grammage_base_unit=excluded.grammage_base_unit,
                   pack_units=excluded.pack_units, image_url=excluded.image_url,
                   last_seen_run=excluded.last_seen_run, raw_json=excluded.raw_json""",
            {**p, "first_seen": first_seen, "last_seen": run_id},
        )

    # fields that define a distinct "price state" — a change in any of these
    # writes a new observation row; otherwise we just re-confirm the last one.
    _STATE_FIELDS = ("available", "price", "list_price", "price_no_disc", "in_offer",
                     "best_card_price", "ppum", "saving_text", "promo_text", "grammage_base")

    def add_observation(self, run_id: str, obs: dict, card_prices: list[dict] | None = None):
        """Delta storage: insert a new row only when the state changed vs the
        product's latest observation; otherwise stamp last_seen and bump n_seen.
        Returns ("changed"|"unchanged", obs_id)."""
        prev = self.conn.execute(
            f"""SELECT obs_id, {', '.join(self._STATE_FIELDS)} FROM observations
                WHERE product_key=? ORDER BY captured_at DESC, obs_id DESC LIMIT 1""",
            (obs["product_key"],)).fetchone()

        if prev is not None and all(prev[f] == obs.get(f) for f in self._STATE_FIELDS):
            self.conn.execute(
                "UPDATE observations SET last_seen_run=?, last_seen_at=?, n_seen=n_seen+1 "
                "WHERE obs_id=?", (run_id, obs["captured_at"], prev["obs_id"]))
            return ("unchanged", prev["obs_id"])

        cur = self.conn.execute(
            """INSERT OR IGNORE INTO observations(run_id, product_key, captured_at,
                   last_seen_run, last_seen_at, n_seen,
                   available, price, list_price, price_no_disc, in_offer,
                   best_card_price, best_card_name, ppum, ppum_unit, unit_price_calc,
                   saving_text, promo_text, net_content_raw, grammage_base, raw_json)
               VALUES(:run_id,:product_key,:captured_at,:run_id,:captured_at,1,
                   :available,:price,:list_price,:price_no_disc,:in_offer,
                   :best_card_price,:best_card_name,:ppum,:ppum_unit,:unit_price_calc,
                   :saving_text,:promo_text,:net_content_raw,:grammage_base,:raw_json)""",
            {"run_id": run_id, **obs},
        )
        obs_id = cur.lastrowid
        if card_prices and obs_id:
            self.conn.executemany(
                """INSERT INTO card_prices(obs_id, run_id, product_key, payment_method,
                       promo_name, price, ppum, saving)
                   VALUES(?,?,?,?,?,?,?,?)""",
                [(obs_id, run_id, obs["product_key"], c.get("payment_method"),
                  c.get("promo_name"), c.get("price"), c.get("ppum"), c.get("saving"))
                 for c in card_prices],
            )
        return ("changed", obs_id)

    def add_categories(self, run_id: str, cats: list[dict]):
        self.conn.executemany(
            """INSERT INTO categories(run_id, category_id, name, slug, parent_slug, level, n_products)
               VALUES(?,?,?,?,?,?,?)""",
            [(run_id, c.get("category_id"), c.get("name"), c.get("slug"),
              c.get("parent_slug"), c.get("level"), c.get("n_products"))
             for c in cats],
        )

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.commit()
        self.conn.close()

    # -- merge ------------------------------------------------------------
    def merge_from(self, other_path: str | Path) -> dict:
        """Pull every run (and its rows) from another DB of the same store that
        we don't already have. Idempotent — keyed on run_id."""
        other_path = Path(other_path)
        self.conn.execute("ATTACH DATABASE ? AS src", (str(other_path),))
        try:
            src_store = self.conn.execute("SELECT value FROM src.meta WHERE key='store_slug'").fetchone()
            if src_store and src_store[0] != self.store_slug:
                raise ValueError(f"store mismatch: {src_store[0]} != {self.store_slug}")
            have = {r[0] for r in self.conn.execute("SELECT run_id FROM runs")}
            src_runs = [r[0] for r in self.conn.execute("SELECT run_id FROM src.runs")]
            new_runs = [r for r in src_runs if r not in have]
            for table in ("runs", "observations", "card_prices", "categories"):
                cols = [c[1] for c in self.conn.execute(f"PRAGMA table_info({table})")]
                if table == "observations":
                    cols = [c for c in cols if c != "obs_id"]
                collist = ",".join(cols)
                qmarks = ",".join("?" * len(new_runs))
                self.conn.execute(
                    f"INSERT INTO {table}({collist}) SELECT {collist} FROM src.{table} "
                    f"WHERE run_id IN ({qmarks})", new_runs)
            # refresh product dimension from src (latest-wins by last_seen)
            self.conn.execute("""INSERT OR IGNORE INTO products SELECT * FROM src.products""")
            self.conn.commit()
            return {"new_runs": len(new_runs)}
        finally:
            self.conn.execute("DETACH DATABASE src")
