"""Tiny end-to-end smoke test: scrape 2 categories of Unimarc, dump some rows."""
import io
import sys
import sqlite3
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ojoalcharqui.engine import ScrapeEngine
from ojoalcharqui import config

eng = ScrapeEngine(delay_s=0.4)
run_id = eng.run_store("unimarc", category_limit=2, product_limit_per_cat=8)
print("RUN:", run_id)
print("PROGRESS:", eng.progress("unimarc").message)
print("LOG:")
for line in eng.progress("unimarc").log:
    print("  ", line)

con = sqlite3.connect(config.db_path("unimarc"))
con.row_factory = sqlite3.Row
print("\n-- meta --")
for r in con.execute("SELECT * FROM meta"):
    print(f"  {r['key']}: {r['value']}")
print("\n-- run --")
r = con.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
for k in r.keys():
    print(f"  {k}: {r[k]}")
print("\n-- sample products w/ grammage + unit price --")
for r in con.execute("""
    SELECT p.name, p.ean, p.brand, p.net_content_raw, p.grammage_base, p.grammage_base_unit,
           o.price, o.list_price, o.in_offer, o.ppum, o.unit_price_calc, o.best_card_price
    FROM products p JOIN observations o USING(product_key)
    LIMIT 12"""):
    print(f"  {r['name'][:42]:42} ean={r['ean']} {r['net_content_raw']!s:8} "
          f"base={r['grammage_base']}{r['grammage_base_unit'] or ''} "
          f"price={r['price']} list={r['list_price']} card={r['best_card_price']} "
          f"upc={r['unit_price_calc']}")
print("\n-- card prices sample --")
for r in con.execute("SELECT product_key, payment_method, promo_name, price FROM card_prices LIMIT 6"):
    print(f"  {r['product_key']} {r['payment_method']} {r['price']} :: {r['promo_name'][:40] if r['promo_name'] else ''}")
print("\ncounts:",
      con.execute("SELECT COUNT(*) FROM products").fetchone()[0], "products,",
      con.execute("SELECT COUNT(*) FROM observations").fetchone()[0], "obs,",
      con.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0], "card_prices")
