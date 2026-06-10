"""Testy API kamer. Baza w tmpdir, kamery `enabled=False` (bez ruchu w sieci)."""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    # Świeża baza per test — przeładuj moduły zależne od ścieżki DB.
    monkeypatch.setenv("FACE_DATA_DIR", str(tmp_path))
    import importlib

    import app.config as config

    importlib.reload(config)
    import app.db as db

    importlib.reload(db)
    import app.cameras as cameras

    importlib.reload(cameras)
    import app.routes as routes

    importlib.reload(routes)
    import app.main as main

    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def _payload(**over) -> dict:
    base = {
        "name": "Wejście",
        "source": "front_door",
        "enabled": False,
        "roi": {"shape": "rect", "x": 0.2, "y": 0.3, "w": 0.5, "h": 0.4},
        "interval_seconds": 2.5,
        "motion_threshold": 0.03,
    }
    base.update(over)
    return base


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_crud_cycle(client: TestClient) -> None:
    assert client.get("/api/cameras").json() == []

    created = client.post("/api/cameras", json=_payload())
    assert created.status_code == 201
    cam = created.json()
    cid = cam["id"]
    assert cam["roi"]["shape"] == "rect"

    assert client.get(f"/api/cameras/{cid}").json()["name"] == "Wejście"

    patched = client.patch(
        f"/api/cameras/{cid}",
        json={"roi": {"shape": "poly", "points": [[0.1, 0.1], [0.9, 0.1], [0.5, 0.9]]}},
    )
    assert patched.json()["roi"]["shape"] == "poly"

    assert client.delete(f"/api/cameras/{cid}").status_code == 204
    assert client.get("/api/cameras").json() == []


def test_missing_camera_404(client: TestClient) -> None:
    assert client.get("/api/cameras/999").status_code == 404


def test_roi_out_of_range_422(client: TestClient) -> None:
    bad = client.post(
        "/api/cameras",
        json=_payload(roi={"shape": "rect", "x": 1.5, "y": 0.0, "w": 0.5, "h": 0.5}),
    )
    assert bad.status_code == 422


def test_status_endpoint(client: TestClient) -> None:
    assert client.get("/api/status").json() == []
