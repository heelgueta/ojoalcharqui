"""In-app scheduler: repeat scrapes on an interval while the app is running.

Config persists to data/_schedule.json. A daemon thread wakes every minute and
launches any store whose interval has elapsed (skipping ones already running).

This only fires while the app is open. For always-on scheduling on a server/Pi,
use the headless `scripts/scrape_all.py` from Windows Task Scheduler or cron.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone

from . import config

CONFIG_PATH = config.DATA_DIR / "_schedule.json"
ALLOWED_INTERVALS = {0: "manual", 24: "diario", 168: "semanal", 720: "mensual"}


def _now():
    return datetime.now(timezone.utc)


class Scheduler:
    def __init__(self, engine):
        self.engine = engine
        self._cfg = self._load()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- persistence ------------------------------------------------------
    def _load(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save(self):
        CONFIG_PATH.write_text(json.dumps(self._cfg, indent=2), encoding="utf-8")

    # -- public API -------------------------------------------------------
    def get(self) -> dict:
        return self._cfg

    def set_store(self, slug: str, every_hours: int):
        if every_hours not in ALLOWED_INTERVALS:
            raise ValueError(f"interval must be one of {sorted(ALLOWED_INTERVALS)}")
        entry = self._cfg.setdefault(slug, {})
        entry["every_hours"] = every_hours
        entry["enabled"] = every_hours > 0
        entry.setdefault("last_run", None)
        self._save()
        return entry

    def mark_ran(self, slug: str):
        self._cfg.setdefault(slug, {})["last_run"] = _now().isoformat()
        self._save()

    def status(self) -> list[dict]:
        out = []
        for slug, e in self._cfg.items():
            every = e.get("every_hours", 0)
            last = e.get("last_run")
            next_due = None
            if every and last:
                last_dt = datetime.fromisoformat(last)
                next_due = (last_dt.timestamp() + every * 3600)
            out.append({
                "slug": slug, "every_hours": every,
                "label": ALLOWED_INTERVALS.get(every, f"{every}h"),
                "enabled": e.get("enabled", False),
                "last_run": last,
                "next_due_ts": next_due,
            })
        return out

    # -- loop -------------------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scheduler")
        self._thread.start()

    def _loop(self):
        while not self._stop.wait(60):
            now = _now().timestamp()
            for slug, e in list(self._cfg.items()):
                every = e.get("every_hours", 0)
                if not every or not e.get("enabled"):
                    continue
                if self.engine.is_running(slug):
                    continue
                last = e.get("last_run")
                due = (datetime.fromisoformat(last).timestamp() + every * 3600) if last else 0
                if now >= due:
                    self._launch(slug)

    def _launch(self, slug: str):
        self.mark_ran(slug)

        def worker():
            try:
                self.engine.run_store(slug)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True, name=f"sched-{slug}").start()
