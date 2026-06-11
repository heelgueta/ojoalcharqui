# 👁 ojo al charqui

**Vigilancia longitudinal de precios del retail chileno.** Scrapers + a localhost
app to track supermarket prices over time, compare across chains, and build clean
datasets for consumers, SERNAC, and research.

> *ojo al charqui* — keep an eye on the jerky. These fuckers keep messing with us.

## What it does

- **Scrapes** the big Chilean supermarkets into one SQLite DB per store, with
  rich metadata: prices (normal / oferta / tarjeta), EAN, brand, grammage,
  images, category tree, price-per-unit.
- **Tracks** every scrape run with full provenance (timestamp, scraper version,
  location, coverage, errors) so the longitudinal series is reproducible.
- **Explores** price histories (per-product page with sparkline + full ficha),
  offers, and shrinkflation flags.
- **Estadísticas** — descriptive stats over the latest scrape: price
  distribution histogram, mean/median/SD/IQR, coverage, by-category and
  by-brand breakdowns, and a cross-store overview.
- **Compares** the same product across chains to surface the biggest price gaps
  — by EAN (exact) and by fuzzy matches (brand+grammage+name), so even Jumbo and
  Líder (which expose no clean EAN) enter the comparison.
- **Empareja** — a review queue to confirm/reject fuzzy matches; high-confidence
  pairs auto-confirm. Confirmations build a labeled dataset.
- **Schedules** repeat scrapes (in-app while open, or headless via
  `scripts/scrape_all.py` for an always-on box) so history accumulates.
- **Exports** CSV per store and for the comparador; **snapshots** a dated,
  immutable copy of any store DB for archiving/sharing.

## The app (localhost)

`Tablero` · `Operación` (run + schedule scrapes, live progress) · `Explorador`
(search → product page) · `Comparador` (cross-store gaps) · `Estadísticas` ·
`Emparejador` (matching queue) · `Ofertas` · `Bitácora` (run ledger + snapshots).
Dark "hacker" theme with a light toggle.

## Stores

| Store        | Platform   | Status | EAN | Card prices |
|--------------|------------|--------|-----|-------------|
| Unimarc      | SMU BFF    | ✅     | yes | yes (Unipay tiers) |
| Jumbo        | Cencosud   | ✅     | no  | no |
| Líder        | Walmart    | ✅     | partial | no |
| Acuenta      | Instaleap  | ✅     | yes | no |
| Alvi         | SMU        | ⚠ TODO | – | – |
| Santa Isabel | Cencosud   | ⚠ TODO | – | – |

How each platform was reverse-engineered is in [DECISIONS.md](DECISIONS.md);
raw recon scripts are in [`recon/`](recon/).

## Run it

```bash
pip install -r requirements.txt
python -m ojoalcharqui          # opens http://127.0.0.1:8077
```

Then go to **Operación** and launch a scrape (try *muestra* first — a few
categories — before a *completo* run).

### From the command line

```bash
python scripts/scrape.py unimarc --full          # full catalog, Santiago Centro
python scripts/scrape.py jumbo --cats 3 --per 20  # quick sample
python scripts/scrape_all.py                      # every store, once (for cron/Task Scheduler)
python scripts/peek.py unimarc                    # inspect a store's data
```

### Always-on scheduling

The in-app scheduler (Operación → ⏱ repetir) only fires while the app is open.
For a server/Raspberry Pi, point Windows Task Scheduler or cron at
`python scripts/scrape_all.py` on your chosen cadence.

## Data model

One file per store at `data/<slug>.sqlite` (git-ignored — regenerable):

- `runs` — one row per scrape, with provenance.
- `products` — latest-known catalog dimension (incl. parsed grammage).
- `observations` — **append-only** fact table, one row per product per run
  (prices, availability, grammage snapshot). The longitudinal series lives here.
- `card_prices` — payment-method / club prices per observation.
- `categories` — taxonomy snapshot per run.

DBs are merge-friendly: run ids are UUIDs and product keys are store-native, so
two people's DBs for the same store union without collision
(`StoreDB.merge_from`).

## Politeness

Scraping is deliberately slow and serial per store, with bounded retries. Please
keep it that way — this project is meant to be useful to regulators and
researchers, not to hammer anyone's servers.
