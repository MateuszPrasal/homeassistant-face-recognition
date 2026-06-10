"""Punkt wejścia FastAPI.

Faza 0: REST API (health) + serwowanie statycznego frontu (export Next.js).
Worker ML i reszta API dochodzą w kolejnych fazach.
"""

from fastapi import APIRouter, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import STATIC_DIR

app = FastAPI(title="Rozpoznawanie twarzy", version=__version__)

api = APIRouter(prefix="/api")


@api.get("/health")
def health() -> dict[str, str]:
    """Prosty health-check (dla add-onu i diagnostyki)."""
    return {"status": "ok", "version": __version__}


app.include_router(api)


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
