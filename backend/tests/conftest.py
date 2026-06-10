"""Wspólne fixtury testów.

`client` stawia aplikację na świeżej bazie w tmpdir, z **wyłączoną kaskadą ML**
(FACE_ENABLE_CASCADE=0) — testy API nie ładują modeli ani nie sięgają do sieci.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("FACE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("FACE_ENABLE_CASCADE", "0")

    # Przeładuj moduły zależne od ścieżki DB / configu, w kolejności zależności.
    for name in (
        "app.config",
        "app.db",
        "app.cameras",
        "app.persons",
        "app.routes",
        "app.routes_persons",
        "app.main",
    ):
        importlib.reload(importlib.import_module(name))

    import app.main as main

    with TestClient(main.app) as c:
        yield c
