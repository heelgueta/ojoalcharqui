"""ojoalcharqui — localhost app.

Run:  python -m ojoalcharqui   (or: uvicorn ojoalcharqui.app.server:app --reload)
"""
from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .. import __version__, adapters, matching, queries
from ..engine import ScrapeEngine

HERE = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
app = FastAPI(title="ojo al charqui")
app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")

engine = ScrapeEngine(delay_s=0.6)


# -- jinja filters --------------------------------------------------------
def clp(v):
    if v is None or v == "":
        return "—"
    return "$" + f"{int(v):,}".replace(",", ".")


def short_dt(v):
    if not v:
        return "—"
    return str(v)[:16].replace("T", " ")


templates.env.filters["clp"] = clp
templates.env.filters["short_dt"] = short_dt
templates.env.globals["version"] = __version__


def page(request, name, **ctx):
    ctx["nav_stores"] = queries.available_stores()
    return templates.TemplateResponse(request, name, ctx)


# -- pages ----------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    stores = queries.known_stores()
    totals = {
        "products": sum(s["n_products"] for s in stores),
        "runs": sum(s["n_runs"] for s in stores),
        "stores_live": sum(1 for s in stores if s["n_products"]),
    }
    return page(request, "dashboard.html", stores=stores, totals=totals)


@app.get("/operacion", response_class=HTMLResponse)
def operacion(request: Request):
    return page(request, "operacion.html", stores=queries.known_stores())


@app.get("/bitacora", response_class=HTMLResponse)
def bitacora(request: Request):
    return page(request, "bitacora.html", runs=queries.all_runs())


@app.get("/explorador", response_class=HTMLResponse)
def explorador(request: Request, store: str = "", q: str = "", offers: int = 0):
    stores = queries.available_stores()
    if not store and stores:
        store = stores[0]["slug"]
    results = queries.search_products(store, q, only_offers=bool(offers)) if store else []
    return page(request, "explorador.html", stores=stores, store=store, q=q,
                offers=offers, results=results)


@app.get("/producto/{store}/{product_key}", response_class=HTMLResponse)
def producto(request: Request, store: str, product_key: str):
    detail = queries.product_detail(store, product_key)
    return page(request, "producto.html", store=store, detail=detail)


@app.get("/comparador", response_class=HTMLResponse)
def comparador(request: Request, sort: str = "gap_pct"):
    rows = queries.compare_by_ean(sort=sort)
    stores = [s for s in queries.available_stores() if s["n_products"] > 0]
    return page(request, "comparador.html", rows=rows, stores=stores, sort=sort)


@app.get("/emparejador", response_class=HTMLResponse)
def emparejador(request: Request):
    return page(request, "emparejador.html",
                stats=matching.stats(), queue=matching.candidate_queue(limit=30))


@app.post("/api/match/rebuild")
def match_rebuild():
    return matching.rebuild_all()


@app.post("/api/match/candidate/{cand_id}")
def match_candidate(cand_id: int, status: str):
    if status not in ("confirmed", "rejected"):
        return JSONResponse({"error": "bad status"}, status_code=400)
    matching.set_candidate_status(cand_id, status)
    return {"cand_id": cand_id, "status": status}


@app.get("/ofertas", response_class=HTMLResponse)
def ofertas(request: Request, store: str = ""):
    stores = queries.available_stores()
    if not store and stores:
        store = stores[0]["slug"]
    rows = queries.offers(store) if store else []
    return page(request, "ofertas.html", stores=stores, store=store, rows=rows)


# -- scrape control API ---------------------------------------------------
@app.post("/api/scrape/{slug}")
def start_scrape(slug: str, full: int = 1):
    try:
        adapters.get(slug)
    except KeyError:
        return JSONResponse({"error": f"unknown store {slug}"}, status_code=404)
    if engine.is_running(slug):
        return JSONResponse({"error": "already running"}, status_code=409)
    kwargs = {} if full else {"category_limit": 3, "product_limit_per_cat": 20}

    def worker():
        try:
            engine.run_store(slug, **kwargs)
        except Exception:
            pass

    threading.Thread(target=worker, daemon=True, name=f"scrape-{slug}").start()
    return {"started": slug, "mode": "full" if full else "sample"}


@app.post("/api/scrape/{slug}/stop")
def stop_scrape(slug: str):
    engine.request_stop(slug)
    return {"stopping": slug}


@app.get("/api/progress")
def progress():
    return engine.all_progress()


# -- export / snapshots ---------------------------------------------------
def _csv_response(text: str, filename: str):
    return PlainTextResponse(text, media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/export/comparador.csv")
def export_comparador():
    return _csv_response(queries.export_comparador_csv(), "comparador.csv")


@app.get("/export/{store}.csv")
def export_store(store: str):
    return _csv_response(queries.export_store_csv(store), f"{store}.csv")


@app.post("/api/snapshot/{store}")
def snapshot(store: str):
    try:
        return queries.make_snapshot(store)
    except FileNotFoundError:
        return JSONResponse({"error": "no data for store"}, status_code=404)


@app.get("/api/progress/{slug}")
def progress_one(slug: str):
    p = engine.progress(slug)
    return p.snapshot() if p else {"status": "idle", "store": slug}
