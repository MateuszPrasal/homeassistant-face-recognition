"""Dopasowanie embeddingu do galerii — cosine similarity, brute-force numpy.

Embeddingi są L2-znormalizowane (recognize.py), więc cosine = iloczyn skalarny.
Skala domowa (kilka osób, kilkadziesiąt wektorów) — żaden vector-DB niepotrzebny.
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class Match:
    known: bool
    person_id: int | None
    name: str | None
    score: float  # najlepszy cosine (także gdy poniżej progu)


def match(
    embedding: np.ndarray,
    gallery: list[tuple[int, str, np.ndarray]],
    threshold: float,
) -> Match:
    """Najlepsze dopasowanie embeddingu do galerii. Pusta galeria → nieznany."""
    if not gallery:
        return Match(known=False, person_id=None, name=None, score=0.0)

    matrix = np.stack([emb for _, _, emb in gallery])  # (M, 512)
    scores = matrix @ embedding  # cosine (wektory znormalizowane)
    best = int(np.argmax(scores))
    best_score = float(scores[best])
    pid, name, _ = gallery[best]

    if best_score >= threshold:
        return Match(known=True, person_id=pid, name=name, score=best_score)
    return Match(known=False, person_id=None, name=None, score=best_score)
