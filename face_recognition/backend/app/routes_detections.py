"""REST API logu detekcji (Faza 6) — podgląd zdarzeń i strojenie progu cosine.

`GET /api/detections` — ostatnie wpisy (czas, kamera, outcome, score, imię).
`GET /api/detections/{id}/snapshot` — zdjęcie ALERT-u (jeśli było zapisane).
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response

from . import detections as repo
from .config import ALERTS_DIR
from .schemas import Detection

router = APIRouter(prefix="/api")


@router.get("/detections", response_model=list[Detection])
def list_detections(
    limit: int = Query(default=50, ge=1, le=500),
    camera_id: int | None = Query(default=None),
) -> list[Detection]:
    return repo.list_detections(limit=limit, camera_id=camera_id)


@router.get("/detections/{detection_id}/snapshot")
def detection_snapshot(detection_id: int) -> Response:
    """Serwuje zapisany snapshot wpisu. Ścieżka musi leżeć w ALERTS_DIR (ochrona
    przed wyjściem poza katalog), plik musi istnieć."""
    path = repo.snapshot_path(detection_id)
    if not path:
        raise HTTPException(status_code=404, detail="Brak zdjęcia dla tej detekcji.")
    resolved = Path(path).resolve()
    alerts_root = ALERTS_DIR.resolve()
    if not resolved.is_relative_to(alerts_root) or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Zdjęcie niedostępne.")
    return Response(content=resolved.read_bytes(), media_type="image/jpeg")
