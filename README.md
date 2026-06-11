# 👁 ojo al charqui

**Vigilancia longitudinal de precios del retail chileno.** Scrapers + a localhost
app to track Chilean supermarket prices over time, compare across chains, and
build clean datasets for consumers, SERNAC, and research.

> *ojo al charqui* — "keep an eye on the jerky." A Chilean way of saying: watch
> closely, because the prices keep shifting on you.

## What it does

- **Scrapes** the big Chilean supermarkets into one SQLite DB per store, with
  rich metadata: prices (normal / oferta / tarjeta), EAN, brand, grammage,
  images, category tree, price-per-unit.
- **Tracks** every scrape run with full provenance (timestamp, scraper version,
  location, coverage, errors) so the longitudinal series is reproducible.
- **Stores changes only** — a re-scrape writes a new observation only when a
  product's state actually changed; otherwise it just records "checked at this
  time, still the same." Keeps the DBs small as history accumulates.
- **Explores** the catalog: search across all chains at once, sort by price,
  open a per-product page with price-history sparkline, card-tier prices,
  cross-store comparison, and a deep link to the original store page.
- **Compares** the same product across chains to surface the biggest price gaps —
  by EAN (exact) and by fuzzy matches (brand+grammage+name), so even Jumbo and
  Líder (which expose no clean EAN) enter the comparison. Guards against
  mislabeled barcodes (different sizes sharing an EAN) and shows card/club prices.
- **Variación** — the same product, how much its price moved over time (needs ≥2
  scrapes). The longitudinal view; fills in as scrapes accumulate.
- **Estadísticas** — descriptive stats over the latest scrape: price-distribution
  histogram, mean/median/SD/IQR, data coverage, by-category and by-brand
  breakdowns, and a cross-store overview.
- **Empareja** — a review queue to confirm/reject fuzzy matches; high-confidence
  pairs auto-confirm. Confirmations build a labeled dataset.
- **Schedules** repeat scrapes (in-app while open, or headless for an always-on
  box) so history accumulates.
- **Exports** CSV per store and for the comparador; **snapshots** a dated,
  immutable copy of any store DB for archiving/sharing/syncing.

## The app (localhost)

`Tablero` · `Operación` (run + schedule scrapes, live progress) · `Explorador`
(search all chains, sort by price → product page) · `Comparador` (cross-store
gaps) · `Variación` (price change over time) · `Estadísticas` · `Emparejador`
(matching queue) · `Ofertas` · `Bitácora` (run ledger + snapshots).
Dark "hacker" theme with a light toggle.

## Stores

| Store        | Platform   | Status | EAN | Card prices |
|--------------|------------|--------|-----|-------------|
| Unimarc      | SMU BFF    | ✅     | yes | yes (Unipay tiers) |
| Jumbo        | Cencosud   | ✅     | no  | no |
| Líder        | Walmart    | ✅     | partial | no |
| Acuenta      | Instaleap  | ✅     | yes | no |
| Santa Isabel | Cencosud   | parked | – | – |
| Alvi         | SMU        | parked | – | – |

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
python scripts/scrape.py unimarc --full           # full catalog, Santiago Centro
python scripts/scrape.py jumbo --cats 3 --per 20  # quick sample
python scripts/scrape_all.py                      # every store, once (for cron/Task Scheduler)
python scripts/peek.py unimarc                     # inspect a store's data
```

### Always-on scheduling

The in-app scheduler (Operación → ⏱ repetir) only fires while the app is open.
For a server/Raspberry Pi, point Windows Task Scheduler or cron at
`python scripts/scrape_all.py` on your chosen cadence.

## Data model

One file per store at `data/<slug>.sqlite` (git-ignored — regenerable):

- `runs` — one row per scrape, with provenance (incl. `n_changed`/`n_unchanged`).
- `products` — latest-known catalog dimension (incl. parsed grammage,
  `last_seen_run`).
- `observations` — **change-log** fact table: one row per *price state* per
  product. A new row is written only when something changed; an unchanged
  re-scrape stamps `last_seen_at` and bumps `n_seen`. The price history is the
  sequence of rows, each valid `[captured_at, last_seen_at]`.
- `card_prices` — payment-method / club prices per observation.
- `categories` — taxonomy snapshot per run.

DBs are **merge-friendly**: run ids are UUIDs and product keys are store-native,
so two machines' DBs for the same store union without collision
(`StoreDB.merge_from`). Schema auto-migrates older DBs on open.

## Syncing between computers (no re-scraping)

DBs are intentionally **not** committed to git (they are large binaries that
bloat history). To move data between machines without re-scraping, use
`scripts/sync.py` — it snapshots, merges, and (optionally) pushes/pulls via
[rclone](https://rclone.org):

```bash
python scripts/sync.py snapshot            # freeze each store DB into data/snapshots/
python scripts/sync.py merge <dir-or.sqlite>   # fold another machine's data in (idempotent)
python scripts/sync.py push / pull          # rclone <-> a cloud remote (set OAC_RCLONE_REMOTE)
```

Transport is your choice — rclone+Backblaze B2, a Drive/Dropbox synced
*snapshots* folder, or a private Git-LFS repo. Always sync **snapshots**, never a
live DB that's being written. `merge` is idempotent and keyed on run id.

## Politeness

Scraping is deliberately slow and serial per store, with bounded retries. Please
keep it that way — this project is meant to be useful to regulators and
researchers, not to overload anyone's servers.
