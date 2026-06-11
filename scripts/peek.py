"""Quick data peek: python scripts/inspect.py <slug> [n]"""
import io, sys, sqlite3
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ojoalcharqui import config

slug = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 14
con = sqlite3.connect(config.db_path(slug)); con.row_factory = sqlite3.Row
print("counts:",
      con.execute("SELECT COUNT(*) FROM products").fetchone()[0], "products,",
      con.execute("SELECT COUNT(*) FROM observations").fetchone()[0], "obs,",
      con.execute("SELECT COUNT(*) FROM card_prices").fetchone()[0], "cards,",
      con.execute("SELECT COUNT(*) FROM products WHERE ean IS NOT NULL AND ean<>''").fetchone()[0], "w/ean")
print()
sql = """SELECT p.name,p.brand,p.ean,p.grammage_base,p.grammage_base_unit,p.image_url,
                o.price,o.list_price,o.in_offer,o.best_card_price,o.unit_price_calc
         FROM products p JOIN observations o USING(product_key) LIMIT ?"""
for r in con.execute(sql, (n,)):
    img = "Y" if r["image_url"] else "N"
    gb = f"{r['grammage_base']}{r['grammage_base_unit'] or ''}" if r["grammage_base"] else "-"
    print(f"{(r['name'] or '')[:38]:38} | {(r['brand'] or '')[:14]:14} | ean={r['ean'] or '-':>13} | "
          f"{gb:>9} | ${r['price']} list={r['list_price']} off={r['in_offer']} "
          f"card={r['best_card_price']} upc={r['unit_price_calc']} img={img}")
