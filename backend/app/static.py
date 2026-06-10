"""Serwowanie statycznego frontu (export Next.js) z obsługą Ingress.

Pod Ingress HA front ładuje się spod dynamicznego prefiksu
`/api/hassio_ingress/<token>/`. Ścieżki assetów są **względne** (robi to
`frontend/scripts/relativize.mjs`), a tu dokładamy `<base href>` z nagłówka
`X-Ingress-Path`, żeby rozwiązywały się względem właściwego prefiksu. Bez
Ingress (dev/bezpośrednio) baza = `/` i nic się nie zmienia.

Tylko dokument wejściowy (`index.html`) dostaje `<base href>` — to jedyna trasa
SPA (zakładki po stronie Reacta, bez routingu klienta). Reszta to assety,
serwowane przez StaticFiles bez modyfikacji.
"""

import html as _html
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger("face.static")


def _base_href(request: Request) -> str:
    """Prefiks Ingress z nagłówka (bez końcowego slasha) → baza z slashem."""
    prefix = request.headers.get("X-Ingress-Path", "").strip()
    if not prefix:
        return "/"
    return prefix.rstrip("/") + "/"


def _inject_base(html_text: str, base: str) -> str:
    """Wstawia <base href> zaraz po <head>, przed jakimkolwiek URL-em w head."""
    tag = f'<base href="{_html.escape(base, quote=True)}">'
    lower = html_text.lower()
    idx = lower.find("<head>")
    if idx == -1:
        return html_text  # brak <head> — nie ruszamy
    end = idx + len("<head>")
    return html_text[:end] + tag + html_text[end:]


def mount_frontend(app: FastAPI, static_dir: Path) -> None:
    """Rejestruje trasę `/` (index z base href) + StaticFiles dla assetów."""
    index_path = static_dir / "index.html"
    index_html = index_path.read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        body = _inject_base(index_html, _base_href(request))
        # no-store: prefiks Ingress (token) bywa różny — nie cache'uj dokumentu.
        return HTMLResponse(body, headers={"Cache-Control": "no-store"})

    # Reszta (assety _next, favicon, …) — bez modyfikacji. html=True podaje
    # index.html dla katalogów, ale trasę `/` przejmuje handler wyżej.
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    log.info("Front serwowany z %s (Ingress: base href z X-Ingress-Path).", static_dir)
