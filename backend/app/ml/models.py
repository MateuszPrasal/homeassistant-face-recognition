"""Zarządzanie plikami modeli ONNX.

Trzymamy trzy modele:
- `ssd_mobilenet_v1_10.onnx` — detektor osoby (COCO, klasa person=1), permisywny,
- `det_500m.onnx` — SCRFD (detekcja twarzy z buffalo_s),
- `w600k_mbf.onnx` — ArcFace (embedding 512-d z buffalo_s).

`ensure_models()` dociąga brakujące pliki do MODELS_DIR. buffalo_s jest w jednym
ZIP-ie (z dużym 1k3d68.onnx, którego NIE potrzebujemy) — wypakowujemy tylko dwa
modele. W add-onie MODELS_DIR powinien wskazywać na /data/models (trwałość),
ewentualnie pliki da się wgrać do obrazu na etapie Fazy 5.
"""

import io
import logging
import zipfile

import httpx

from ..config import MODELS_DIR

log = logging.getLogger("face.models")

SSD = "ssd_mobilenet_v1_10.onnx"
SCRFD = "det_500m.onnx"
ARCFACE = "w600k_mbf.onnx"

_SSD_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/"
    "object_detection_segmentation/ssd-mobilenetv1/model/ssd_mobilenet_v1_10.onnx"
)
_BUFFALO_URL = (
    "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_s.zip"
)


def path(name: str):
    """Ścieżka do pliku modelu w MODELS_DIR."""
    return MODELS_DIR / name


def models_present() -> bool:
    """Czy wszystkie wymagane modele są na dysku."""
    return all(path(n).exists() for n in (SSD, SCRFD, ARCFACE))


def _download(url: str) -> bytes:
    log.info("Pobieram model: %s", url)
    with httpx.Client(timeout=180, follow_redirects=True) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return resp.content


def ensure_models() -> None:
    """Dociąga brakujące modele. Idempotentne — gotowe pliki pomija."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    if not path(SSD).exists():
        path(SSD).write_bytes(_download(_SSD_URL))

    if not (path(SCRFD).exists() and path(ARCFACE).exists()):
        log.info("Pobieram buffalo_s (wypakuję %s + %s)…", SCRFD, ARCFACE)
        with zipfile.ZipFile(io.BytesIO(_download(_BUFFALO_URL))) as z:
            for name in (SCRFD, ARCFACE):
                if not path(name).exists():
                    path(name).write_bytes(z.read(name))

    log.info("Modele gotowe w %s", MODELS_DIR)
