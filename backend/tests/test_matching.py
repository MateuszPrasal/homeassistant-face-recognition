"""Testy dopasowania cosine (czysta logika, bez modeli)."""

import numpy as np

from app.matching import match


def _unit(*vals) -> np.ndarray:
    v = np.array(vals, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_empty_gallery_unknown() -> None:
    m = match(_unit(1, 0, 0), [], threshold=0.4)
    assert m.known is False and m.score == 0.0


def test_known_above_threshold() -> None:
    q = _unit(1, 0, 0)
    gallery = [(7, "Ala", _unit(0.99, 0.1, 0.0)), (8, "Ola", _unit(0, 1, 0))]
    m = match(q, gallery, threshold=0.4)
    assert m.known is True and m.person_id == 7 and m.name == "Ala"
    assert m.score > 0.9


def test_below_threshold_unknown_but_reports_score() -> None:
    q = _unit(1, 0, 0)
    gallery = [(1, "X", _unit(0.3, 1, 0))]  # cosine ~0.29
    m = match(q, gallery, threshold=0.4)
    assert m.known is False and m.person_id is None
    assert 0.0 < m.score < 0.4
