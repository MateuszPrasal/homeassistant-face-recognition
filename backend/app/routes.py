"""REST API kamer (Faza 1).

CRUD na kamerach + podgląd statusu workerów i pojedynczego snapshotu. Każda
mutacja konfiguracji przeładowuje workera danej kamery, żeby pętla od razu
działała na nowych ustawieniach (źródło / ROI / interwał).
"""

from dataclasses import asdict

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status

from . import cameras as repo
from .schemas import Camera, CameraCreate, CameraUpdate
from .snapshot import SnapshotClient
from .worker import WorkerManager

router = APIRouter(prefix="/api")


def _manager(request: Request) -> WorkerManager:
    return request.app.state.manager


@router.get("/cameras", response_model=list[Camera])
def list_cameras() -> list[Camera]:
    return repo.list_cameras()


@router.post("/cameras", response_model=Camera, status_code=status.HTTP_201_CREATED)
def create_camera(data: CameraCreate, request: Request) -> Camera:
    camera = repo.create_camera(data)
    _manager(request).start_camera(camera)
    return camera


@router.get("/cameras/{camera_id}", response_model=Camera)
def get_camera(camera_id: int) -> Camera:
    camera = repo.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej kamery.")
    return camera


@router.patch("/cameras/{camera_id}", response_model=Camera)
def update_camera(camera_id: int, data: CameraUpdate, request: Request) -> Camera:
    camera = repo.update_camera(camera_id, data)
    if camera is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej kamery.")
    _manager(request).start_camera(camera)  # reload z nową konfiguracją
    return camera


@router.delete("/cameras/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_camera(camera_id: int, request: Request) -> Response:
    if not repo.delete_camera(camera_id):
        raise HTTPException(status_code=404, detail="Nie ma takiej kamery.")
    _manager(request).stop_camera(camera_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/cameras/{camera_id}/snapshot")
def camera_snapshot(camera_id: int) -> Response:
    """Pobiera bieżącą klatkę z go2rtc (diagnostyka źródła / podgląd w UI)."""
    camera = repo.get_camera(camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej kamery.")
    client = SnapshotClient()
    try:
        data = client.fetch(camera.source)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Błąd pobrania snapshotu: {exc}") from exc
    finally:
        client.close()
    return Response(content=data, media_type="image/jpeg")


@router.get("/status")
def status_overview(request: Request) -> list[dict]:
    """Status workerów per kamera — do podglądu „ruch/brak ruchu" w Fazie 1."""
    return [asdict(s) for s in _manager(request).status().values()]
