"""Testy logiki decyzyjnej kaskady (tabela outcome'ów) — bez modeli.

Podstawiamy atrybuty detektorów/recognizera atrapami i kontrolujemy wynik
dopasowania, żeby sprawdzić samą logikę wyznaczania `outcome` i priorytety.
"""

import types

import numpy as np

from app.cascade import Cascade
from app.matching import Match
from app.ml.face import Face
from app.ml.person import PersonBox
from app.roi import DEFAULT_ROI


def _face() -> Face:
    return Face(x1=0, y1=0, x2=10, y2=10, score=0.9, kps=np.zeros((5, 2), dtype=np.float32))


def _build(monkeypatch, person_boxes, faces, match_results) -> Cascade:
    c = Cascade.__new__(Cascade)  # bez __init__ (nie ładujemy modeli)
    c.threshold = 0.4
    c.person = types.SimpleNamespace(detect=lambda crop: person_boxes)
    c.face = types.SimpleNamespace(detect=lambda img: list(faces))
    c.recognizer = types.SimpleNamespace(
        embed=lambda img, kps: np.zeros(512, dtype=np.float32)
    )
    monkeypatch.setattr("app.cascade.persons.load_gallery", lambda: [])
    results = iter(match_results)
    monkeypatch.setattr("app.cascade.matching.match", lambda e, g, t: next(results))
    return c


_FRAME = np.zeros((100, 100, 3), dtype=np.uint8)
_BOX = PersonBox(x1=0, y1=0, x2=50, y2=50, score=0.9)
_KNOWN = Match(known=True, person_id=1, name="Ala", score=0.8)
_UNKNOWN = Match(known=False, person_id=None, name=None, score=0.1)


def test_no_person_none(monkeypatch) -> None:
    c = _build(monkeypatch, [], [], [])
    assert c.process(_FRAME, DEFAULT_ROI).outcome == "none"


def test_known_face_ok(monkeypatch) -> None:
    c = _build(monkeypatch, [_BOX], [_face()], [_KNOWN])
    res = c.process(_FRAME, DEFAULT_ROI)
    assert res.outcome == "ok" and res.known_name == "Ala"


def test_unknown_face_alert(monkeypatch) -> None:
    c = _build(monkeypatch, [_BOX], [_face()], [_UNKNOWN])
    res = c.process(_FRAME, DEFAULT_ROI)
    assert res.outcome == "unknown_face" and res.alert is True


def test_person_no_face_alert(monkeypatch) -> None:
    c = _build(monkeypatch, [_BOX], [], [])  # osoba, brak twarzy
    res = c.process(_FRAME, DEFAULT_ROI)
    assert res.outcome == "person_no_face" and res.alert is True


def test_priority_unknown_over_known(monkeypatch) -> None:
    # Dwie osoby: jedna znana, jedna nieznana → ALERT unknown_face.
    c = _build(monkeypatch, [_BOX, _BOX], [_face()], [_KNOWN, _UNKNOWN])
    assert c.process(_FRAME, DEFAULT_ROI).outcome == "unknown_face"


def test_priority_no_face_over_known(monkeypatch) -> None:
    # Osoba znana + osoba bez twarzy → ALERT person_no_face.
    boxes = [_BOX, _BOX]
    faces_seq = iter([[_face()], []])  # pierwsza osoba ma twarz, druga nie
    c = Cascade.__new__(Cascade)
    c.threshold = 0.4
    c.person = types.SimpleNamespace(detect=lambda crop: boxes)
    c.face = types.SimpleNamespace(detect=lambda img: next(faces_seq))
    c.recognizer = types.SimpleNamespace(embed=lambda img, kps: np.zeros(512, np.float32))
    monkeypatch.setattr("app.cascade.persons.load_gallery", lambda: [])
    monkeypatch.setattr("app.cascade.matching.match", lambda e, g, t: _KNOWN)
    assert c.process(_FRAME, DEFAULT_ROI).outcome == "person_no_face"
