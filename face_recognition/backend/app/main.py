"""Punkt wejścia FastAPI.

Faza 1: REST API (health + kamery), worker akwizycji w tle (snapshot → gate
ruchu w ROI), serwowanie statycznego frontu (export Next.js). Kaskada ML i MQTT
dochodzą w kolejnych fazach.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from . import __version__
from . import cameras as repo
from . import config
from . import db
from .config import CORS_ORIGINS, ENABLE_CASCADE, STATIC_DIR
from .routes import router as api_router
from .routes_detections import router as detections_router
from .routes_persons import router as persons_router
from .static import mount_frontend
from .worker import WorkerManager

log = logging.getLogger("face")
log.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
# Bez własnego handlera rekordy `face.*` propagują do roota, który nie ma handlera
# (uvicorn konfiguruje tylko swoje loggery), więc INFO przepada — do logów add-onu
# HA (stdout/stderr kontenera) trafiałby tylko WARNING+ przez lastResort. Podpinamy
# StreamHandler na stdout i gasimy propagację, żeby log.info() było widać w HA.
if not log.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%H:%M:%S")
    )
    log.addHandler(_handler)
log.propagate = False
# httpx loguje każdy GET na INFO — w pętli akwizycji to zalew, wycisz do WARNING.
logging.getLogger("httpx").setLevel(logging.WARNING)


def _build_cascade():
    """Dociąga modele i ładuje kaskadę. Przy błędzie → None (tryb sam gate ruchu)."""
    if not ENABLE_CASCADE:
        log.info("Kaskada ML wyłączona (FACE_ENABLE_CASCADE=0) — tylko gate ruchu.")
        return None
    try:
        from .ml import models
        from .cascade import Cascade

        models.ensure_models()
        cascade = Cascade()
        log.info("Kaskada ML gotowa (detektor osoby + twarz + ArcFace).")
        return cascade
    except Exception as exc:  # noqa: BLE001
        log.warning("Nie udało się załadować kaskady ML: %s — tryb sam gate ruchu.", exc)
        return None


def _build_mqtt():
    """Łączy z brokerem MQTT (env lub Supervisor). Przy braku/awarii → None."""
    if not config.MQTT_ENABLE:
        log.info("MQTT wyłączony (FACE_MQTT_ENABLE=0).")
        return None
    try:
        from .mqtt import connect, resolve_config

        cfg = resolve_config(
            host=config.MQTT_HOST,
            port=config.MQTT_PORT,
            username=config.MQTT_USERNAME,
            password=config.MQTT_PASSWORD,
            ssl=config.MQTT_SSL,
            supervisor_token=config.SUPERVISOR_TOKEN,
        )
        if cfg is None:
            log.info("Brak konfiguracji MQTT (env/Supervisor) — publikacja wyłączona.")
            return None
        publisher = connect(
            cfg,
            base_topic=config.MQTT_BASE_TOPIC,
            discovery_prefix=config.MQTT_DISCOVERY_PREFIX,
        )
        log.info("Klient MQTT uruchomiony (broker %s:%s).", cfg.host, cfg.port)
        return publisher
    except Exception as exc:  # noqa: BLE001
        log.warning("Nie udało się uruchomić MQTT: %s — publikacja wyłączona.", exc)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start: baza + modele + MQTT + workery akwizycji. Stop: zatrzymaj wątki."""
    db.init_db()
    mqtt = _build_mqtt()
    manager = WorkerManager(cascade=_build_cascade(), mqtt=mqtt)
    app.state.manager = manager
    manager.start_all(repo.list_cameras())
    try:
        yield
    finally:
        manager.stop_all()
        if mqtt is not None:
            mqtt.close()
        db.close_db()


app = FastAPI(title="Rozpoznawanie twarzy", version=__version__, lifespan=lifespan)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

health = APIRouter(prefix="/api")


@health.get("/health")
def health_check() -> dict[str, str]:
    """Prosty health-check (dla add-onu i diagnostyki)."""
    return {"status": "ok", "version": __version__}


app.include_router(health)
app.include_router(api_router)
app.include_router(persons_router)
app.include_router(detections_router)


# Serwowanie frontu. Pod Ingress prefiks ścieżki jest dynamiczny — `mount_frontend`
# wstrzykuje <base href> z nagłówka X-Ingress-Path do index.html (assety mają
# ścieżki względne dzięki relativize.mjs). Mount na "/" łapie wszystko poza /api.
if (STATIC_DIR / "index.html").is_file():
    mount_frontend(app, STATIC_DIR)
else:

    @app.get("/", response_class=HTMLResponse)
    def placeholder() -> str:
        return (
            "<h1>Backend działa</h1>"
            "<p>Brak zbudowanego frontu — uruchom <code>npm run build:backend</code> "
            "w katalogu <code>frontend/</code>.</p>"
        )
