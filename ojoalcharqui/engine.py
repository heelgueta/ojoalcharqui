"""Scrape engine: polite fetching, retries, run bookkeeping, persistence.

Politeness is non-negotiable in the architecture (Herman's call): a fixed delay
between requests, capped concurrency (we keep it serial per store), bounded
retries with backoff, and an honest identifying User-Agent set by the adapter.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field

import httpx

from . import __version__, adapters, config
from .db import StoreDB, utcnow
from .grammage import parse as parse_grammage


@dataclass
class RunProgress:
    run_id: str = ""
    store: str = ""
    status: str = "idle"            # idle | running | ok | partial | error | stopped
    phase: str = ""                 # categories | scraping | done
    categories_total: int = 0
    categories_done: int = 0
    current_category: str = ""
    products: int = 0
    observations: int = 0
    errors: int = 0
    started_at: str = ""
    finished_at: str = ""
    message: str = ""
    log: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        d = self.__dict__.copy()
        d["log"] = self.log[-40:]
        return d


class ScrapeEngine:
    """One engine instance per process; runs one store at a time per thread.
    The web app keeps a registry of live progress objects keyed by store slug."""

    def __init__(self, delay_s: float = 0.6, timeout: float = 45.0,
                 max_retries: int = 4):
        self.delay_s = delay_s
        self.timeout = timeout
        self.max_retries = max_retries
        self._progress: dict[str, RunProgress] = {}
        self._stop: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    # -- progress access for the UI --------------------------------------
    def progress(self, slug: str) -> RunProgress | None:
        return self._progress.get(slug)

    def all_progress(self) -> dict[str, dict]:
        return {s: p.snapshot() for s, p in self._progress.items()}

    def is_running(self, slug: str) -> bool:
        p = self._progress.get(slug)
        return bool(p and p.status == "running")

    def request_stop(self, slug: str):
        ev = self._stop.get(slug)
        if ev:
            ev.set()

    # -- polite fetch -----------------------------------------------------
    def _make_fetch(self, client: httpx.Client, prog: RunProgress, stop: threading.Event):
        last = [0.0]

        def fetch(method: str, url: str, **kwargs) -> httpx.Response:
            if stop.is_set():
                raise StopScrape()
            # rate limit
            wait = self.delay_s - (time.monotonic() - last[0])
            if wait > 0:
                time.sleep(wait)
            backoff = 1.5
            for attempt in range(self.max_retries):
                try:
                    resp = client.request(method, url, timeout=self.timeout, **kwargs)
                    last[0] = time.monotonic()
                    if resp.status_code in (429, 500, 502, 503, 504):
                        raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                    return resp
                except (httpx.TransportError, httpx.HTTPStatusError) as e:
                    prog.errors += 1
                    if attempt == self.max_retries - 1:
                        prog.log.append(f"giving up on {url}: {e}")
                        raise
                    sleep = backoff ** attempt + 0.5
                    prog.log.append(f"retry {attempt+1} in {sleep:.1f}s ({type(e).__name__})")
                    time.sleep(sleep)
            raise RuntimeError("unreachable")

        return fetch

    # -- run --------------------------------------------------------------
    def run_store(self, slug: str, location_label: str = "Santiago Centro",
                  comuna: str = "Santiago", category_limit: int | None = None,
                  product_limit_per_cat: int | None = None) -> str:
        """Blocking full scrape of one store. Returns run_id."""
        with self._lock:
            if self.is_running(slug):
                raise RuntimeError(f"{slug} already running")
            prog = RunProgress(store=slug, status="running", phase="categories",
                               started_at=utcnow())
            self._progress[slug] = prog
            stop = threading.Event()
            self._stop[slug] = stop

        adapter = adapters.get(slug)
        db = StoreDB(config.db_path(slug), adapter.slug, adapter.name, adapter.platform)
        run_id = db.start_run(
            scraper_version=__version__,
            location_label=location_label, comuna=comuna,
            sales_channel=getattr(adapter, "sales_channel", ""),
            params={"category_limit": category_limit,
                    "product_limit_per_cat": product_limit_per_cat,
                    "delay_s": self.delay_s},
        )
        prog.run_id = run_id
        prog.log.append(f"run {run_id[:8]} started for {adapter.name}")

        n_prod = n_obs = 0
        status = "ok"
        try:
            with httpx.Client(follow_redirects=True, verify=False, http2=True) as client:
                fetch = self._make_fetch(client, prog, stop)
                cats = adapter.categories(client)
                if category_limit:
                    cats = cats[:category_limit]
                prog.categories_total = len(cats)
                prog.phase = "scraping"
                db.add_categories(run_id, [
                    {"category_id": c.category_id, "name": c.name, "slug": c.slug,
                     "parent_slug": c.parent_slug, "level": c.level} for c in cats])
                db.commit()

                for ci, cat in enumerate(cats):
                    if stop.is_set():
                        status = "stopped"
                        break
                    prog.current_category = f"{cat.name} ({cat.slug})"
                    count = 0
                    try:
                        for np in adapter.products_in(client, cat, fetch):
                            self._persist(db, run_id, np)
                            n_prod += 1
                            n_obs += 1
                            count += 1
                            prog.products = n_prod
                            prog.observations = n_obs
                            if product_limit_per_cat and count >= product_limit_per_cat:
                                break
                    except StopScrape:
                        status = "stopped"
                        break
                    except Exception as e:
                        prog.errors += 1
                        prog.log.append(f"category {cat.slug} failed: {e}")
                    prog.categories_done = ci + 1
                    if (ci + 1) % 10 == 0:
                        db.commit()
                db.commit()
        except StopScrape:
            status = "stopped"
        except Exception as e:
            status = "error"
            prog.log.append("FATAL: " + "".join(traceback.format_exception_only(e)).strip())
        finally:
            if status == "ok" and prog.errors > 0:
                status = "partial"
            db.finish_run(run_id, status, n_categories=prog.categories_total,
                          n_products=n_prod, n_observations=n_obs, n_errors=prog.errors)
            db.close()
            prog.status = status
            prog.phase = "done"
            prog.finished_at = utcnow()
            prog.message = f"{status}: {n_prod} products, {prog.errors} errors"
            prog.log.append(prog.message)
        return run_id

    def _persist(self, db: StoreDB, run_id: str, np):
        g = parse_grammage(np.net_content_raw or "", np.name or "")
        unit_price = None
        if np.price and g.base:
            unit_price = round(np.price / g.base, 6)
        prod_row = {
            "product_key": np.product_key, "ean": np.ean, "sku": np.sku,
            "name": np.name, "brand": np.brand, "brand_id": np.brand_id,
            "description": np.description, "category_path": np.category_path,
            "category_slug": np.category_slug, "measurement_unit": np.measurement_unit,
            "net_content_raw": np.net_content_raw, "image_url": np.image_url,
            "raw_json": _json(np.raw),
            **g.as_product_fields(),
        }
        db.upsert_product(prod_row, run_id)
        obs = {
            "product_key": np.product_key, "captured_at": utcnow(),
            "available": int(np.available), "price": np.price,
            "list_price": np.list_price, "price_no_disc": np.price_no_disc,
            "in_offer": int(np.in_offer),
            "best_card_price": np.best_card_price,
            "best_card_name": (np.card_prices[0]["payment_method"] if np.card_prices else None),
            "ppum": np.ppum, "ppum_unit": np.ppum_unit, "unit_price_calc": unit_price,
            "saving_text": np.saving_text, "promo_text": np.promo_text,
            "net_content_raw": np.net_content_raw, "grammage_base": g.base,
            "raw_json": None,
        }
        db.add_observation(run_id, obs, np.card_prices)


class StopScrape(Exception):
    pass


def _json(o) -> str | None:
    import json
    try:
        return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return None
