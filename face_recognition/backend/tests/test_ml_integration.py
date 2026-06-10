"""Test integracyjny kaskady na REALNYCH modelach i zdjęciach.

Domyślnie pomijany (pobranie modeli + zdjęć, wolny). Uruchom lokalnie:
    FACE_IT=1 uv run pytest tests/test_ml_integration.py -v
Wymaga modeli w MODELS_DIR oraz zdjęć testowych w /tmp/faces (obama/biden).
"""

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("FACE_IT") != "1", reason="test integracyjny ML (ustaw FACE_IT=1)"
)

_FACES = Path("/tmp/faces")


@pytest.fixture(scope="module")
def cascade():
    from app.ml import models

    if not models.models_present():
        pytest.skip("brak modeli ONNX w MODELS_DIR")
    if not (_FACES / "obama.jpg").exists():
        pytest.skip("brak zdjęć testowych w /tmp/faces")
    from app.cascade import Cascade

    return Cascade()


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("FACE_DATA_DIR", str(tmp_path))
    import importlib

    import app.config

    importlib.reload(app.config)
    import app.db

    importlib.reload(app.db)
    import app.persons

    importlib.reload(app.persons)
    app.db.init_db()
    yield


def _img(name: str) -> np.ndarray:
    return cv2.imread(str(_FACES / name))


def test_embedding_is_unit_norm(cascade) -> None:
    faces = cascade.face.detect(_img("obama.jpg"))
    emb = cascade.recognizer.embed(_img("obama.jpg"), faces[0].kps)
    assert emb.shape == (512,)
    assert abs(float(np.linalg.norm(emb)) - 1.0) < 1e-3


def test_cascade_outcomes(cascade) -> None:
    import app.persons as persons
    from app.roi import DEFAULT_ROI

    # Enroll Obamę
    p = persons.create_person("Obama")
    faces = cascade.face.detect(_img("obama.jpg"))
    persons.add_face(p.id, cascade.recognizer.embed(_img("obama.jpg"), faces[0].kps))

    assert cascade.process(_img("obama.jpg"), DEFAULT_ROI).outcome == "ok"
    assert cascade.process(_img("biden.jpg"), DEFAULT_ROI).outcome == "unknown_face"
    assert cascade.process(np.zeros((480, 640, 3), np.uint8), DEFAULT_ROI).outcome == "none"
