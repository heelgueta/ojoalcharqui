"""Scrape every known store once, sequentially. Headless — for OS-level
scheduling (Windows Task Scheduler / cron) on an always-on machine.

Usage:
  python scripts/scrape_all.py                 # all stores, full
  python scripts/scrape_all.py unimarc jumbo   # subset
  python scripts/scrape_all.py --sample        # quick (few cats each)
"""
import io
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ojoalcharqui import adapters
from ojoalcharqui.engine import ScrapeEngine


def main(argv):
    sample = "--sample" in argv
    wanted = [a for a in argv if not a.startswith("--")]
    slugs = wanted or adapters.all_slugs()
    eng = ScrapeEngine(delay_s=0.5)
    kw = {"category_limit": 3, "product_limit_per_cat": 20} if sample else {}
    print(f"== scrape_all: {slugs} {'(sample)' if sample else '(full)'} ==", flush=True)
    summary = []
    for slug in slugs:
        try:
            adapters.get(slug)
        except KeyError:
            print(f"  skip unknown {slug}", flush=True)
            continue
        t0 = time.time()
        print(f"\n-- {slug} --", flush=True)
        try:
            eng.run_store(slug, **kw)
            p = eng.progress(slug)
            summary.append((slug, p.status, p.products, p.errors, round(time.time() - t0)))
            print(f"   {p.message}", flush=True)
        except Exception as e:
            summary.append((slug, "error", 0, 0, round(time.time() - t0)))
            print(f"   FAILED: {e}", flush=True)
    print("\n== summary ==")
    for slug, st, n, err, dur in summary:
        print(f"  {slug:12} {st:8} {n:6} products  {err} err  {dur}s")


if __name__ == "__main__":
    main(sys.argv[1:])
