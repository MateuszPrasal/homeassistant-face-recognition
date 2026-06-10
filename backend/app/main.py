"""Punkt wejścia FastAPI.

Faza 1: REST API (health + kamery), worker akwizycji w tle (snapshot → gate
ruchu w ROI), serwowanie statycznego frontu (export Next.js). Kaskada ML i MQTT
dochodzą w kolejnych fazach.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from . import cameras as repo
from . import db
from .config import STATIC_DIR
from .routes import router as api_router
from .worker import WorkerManager

logging.getLogger("face").setLevel(logging.INFO)
# httpx loguje każdy GET na INFO — w pętli akwizycji to zalew, wycisz do WARNING.
logging.getLogger("httpx").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start: baza + workery akwizycji dla włączonych kamer. Stop: zatrzymaj wątki."""
    db.init_db()
    manager = WorkerManager()
    app.state.manager = manager
    manager.start_all(repo.list_cameras())
    try:
        yield
    finally:
        manager.stop_all()
        db.close_db()


app = FastAPI(title="Rozpoznawanie twarzy", version=__version__, lifespan=lifespan)

health = APIRouter(prefix="/api")


@health.get("/health")
def health_check() -> dict[str, str]:
    """Prosty health-check (dla add-onu i diagnostyki)."""
    return {"status": "ok", "version": __version__}


app.include_router(health)
app.include_router(api_router)


# Serwowanie frontu. Mount na "/" łapie wszystko, co nie trafiło wcześniej do /api.
# StaticFiles(html=True) podaje index.html dla katalogów (trasy Next z trailingSlash).
#
# TODO (Faza 5 — Ingress): pod Ingress prefiks ścieżki jest dynamiczny, więc tu
# dojdzie wstrzykiwanie <base href> z nagłówka X-Ingress-Path do odpowiedzi HTML.
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
else:

    @app.get("/", response_class=HTMLResponse)
    def placeholder() -> str:
        return (
            "<h1>Backend działa</h1>"
            "<p>Brak zbudowanego frontu — uruchom <code>npm run build:backend</code> "
            "w katalogu <code>frontend/</code>.</p>"
        )
