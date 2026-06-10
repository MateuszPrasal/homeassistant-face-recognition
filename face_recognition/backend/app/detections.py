"""Repozytorium logu detekcji (Faza 6).

Wpis powstaje przy każdej wykrytej osobie (outcome != none) — do strojenia progu
cosine i podglądu „co widziała kamera". Log przycinamy do ostatnich
`MAX_DETECTIONS` wpisów (skala domowa — nie chcemy, by /data puchło).

`matched_name` trzymamy denormalizowane: po usunięciu osoby `matched_person_id`
leci na NULL (FK ON DELETE SET NULL), ale nazwa zostaje w historii.
"""

import sqlite3
from pathlib import Path

from . import db
from .config import ALERTS_DIR, MAX_DETECTIONS
from .schemas import Detection


def _unlink_snapshot(path: str | None) -> None:
    """Kasuje plik snapshotu przyciętego wpisu. Tylko w ALERTS_DIR (ochrona przed
    wyjściem poza katalog); błędy IO ignorujemy — to sprzątanie, nie krytyczna ścieżka."""
    if not path:
        return
    try:
        resolved = Path(path).resolve()
        if resolved.is_relative_to(ALERTS_DIR.resolve()) and resolved.is_file():
            resolved.unlink()
    except OSError:
        pass


def _row_to_detection(row: sqlite3.Row) -> Detection:
    return Detection(
        id=row["id"],
        camera_id=row["camera_id"],
        created_at=row["created_at"],
        person_detected=bool(row["person_detected"]),
        face_detected=bool(row["face_detected"]),
        matched_person_id=row["matched_person_id"],
        matched_name=row["matched_name"],
        score=row["score"],
        outcome=row["outcome"],
        has_snapshot=bool(row["snapshot_path"]),
    )


def add_detection(
    *,
    camera_id: int,
    person_detected: bool,
    face_detected: bool,
    matched_person_id: int | None,
    matched_name: str | None,
    score: float,
    outcome: str,
    snapshot_path: str | None,
) -> int:
    """Dopisuje wpis i przycina log do MAX_DETECTIONS. Zwraca id wpisu."""
    pruned_paths: list[str | None] = []
    with db.transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO detections
                (camera_id, person_detected, face_detected, matched_person_id,
                 matched_name, score, outcome, snapshot_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                camera_id,
                int(person_detected),
                int(face_detected),
                matched_person_id,
                matched_name,
                float(score),
                outcome,
                snapshot_path,
            ),
        )
        det_id = cur.lastrowid
        if MAX_DETECTIONS > 0:
            # Zostaw ostatnie N (po id). Tanie przy skali domowej. Ścieżki snapshotów
            # przycinanych wpisów zbieramy, żeby skasować pliki po commicie.
            pruned_paths = [
                r["snapshot_path"]
                for r in conn.execute(
                    """
                    SELECT snapshot_path FROM detections WHERE id <= (
                        SELECT id FROM detections ORDER BY id DESC LIMIT 1 OFFSET ?
                    )
                    """,
                    (MAX_DETECTIONS,),
                ).fetchall()
            ]
            conn.execute(
                """
                DELETE FROM detections WHERE id <= (
                    SELECT id FROM detections ORDER BY id DESC
                    LIMIT 1 OFFSET ?
                )
                """,
                (MAX_DETECTIONS,),
            )
    for path in pruned_paths:
        _unlink_snapshot(path)
    return int(det_id)


def list_detections(limit: int = 50, camera_id: int | None = None) -> list[Detection]:
    """Ostatnie wpisy (malejąco po id), opcjonalnie filtr po kamerze."""
    limit = max(1, min(limit, 500))
    with db.transaction() as conn:
        if camera_id is None:
            rows = conn.execute(
                "SELECT * FROM detections ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM detections WHERE camera_id = ? ORDER BY id DESC LIMIT ?",
                (camera_id, limit),
            ).fetchall()
    return [_row_to_detection(r) for r in rows]


def snapshot_path(detection_id: int) -> str | None:
    """Ścieżka snapshotu danego wpisu (do serwowania zdjęcia) albo None."""
    with db.transaction() as conn:
        row = conn.execute(
            "SELECT snapshot_path FROM detections WHERE id = ?", (detection_id,)
        ).fetchone()
    return row["snapshot_path"] if row else None
