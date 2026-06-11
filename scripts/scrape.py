"""CLI scraper. Usage:
  python scripts/scrape.py <slug> [--full | --cats N --per M]
"""
import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ojoalcharqui.engine import ScrapeEngine

ap = argparse.ArgumentParser()
ap.add_argument("slug")
ap.add_argument("--full", action="store_true")
ap.add_argument("--cats", type=int, default=3)
ap.add_argument("--per", type=int, default=None)
ap.add_argument("--delay", type=float, default=0.6)
a = ap.parse_args()

eng = ScrapeEngine(delay_s=a.delay)
kw = {} if a.full else {"category_limit": a.cats, "product_limit_per_cat": a.per}
print(f"scraping {a.slug} {'(FULL)' if a.full else kw} delay={a.delay}s")
run_id = eng.run_store(a.slug, **kw)
p = eng.progress(a.slug)
print(f"\n{p.message}\nrun={run_id}")
print("last log:")
for line in p.log[-6:]:
    print("  ", line)
