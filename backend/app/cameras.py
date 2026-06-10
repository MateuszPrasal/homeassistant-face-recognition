"""Repozytorium kamer — CRUD na tabeli `cameras`.

ROI serializujemy do JSON przy zapisie i parsujemy z powrotem przy odczycie
(TypeAdapter ogarnia dyskryminowaną unię rect/poly).
"""

import sqlite3

from pydantic import TypeAdapter

from . import db
from .roi import ROI
from .schemas import Camera, CameraCreate, CameraUpdate

_roi_adapter: TypeAdapter = TypeAdapter(ROI)


def _row_to_camera(row: sqlite3.Row) -> Camera:
    return Camera(
        id=row["id"],
        name=row["name"],
        source=row["source"],
        roi=_roi_adapter.validate_json(row["roi"]),
        interval_seconds=row["interval_seconds"],
        cooldown_seconds=row["cooldown_seconds"],
        motion_threshold=row["motion_threshold"],
        enabled=bool(row["enabled"]),
        created_at=row["created_at"],
    )


def list_cameras() -> list[Camera]:
    with db.transaction() as conn:
        rows = conn.execute("SELECT * FROM cameras ORDER BY id").fetchall()
    return [_row_to_camera(r) for r in rows]


def get_camera(camera_id: int) -> Camera | None:
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    return _row_to_camera(row) if row else None


def create_camera(data: CameraCreate) -> Camera:
    roi_json = _roi_adapter.dump_json(data.roi).decode()
    with db.transaction() as conn:
        cur = conn.execute(
            """
            INSERT INTO cameras
                (name, source, roi, interval_seconds, cooldown_seconds,
                 motion_threshold, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.name,
                data.source,
                roi_json,
                data.interval_seconds,
                data.cooldown_seconds,
                data.motion_threshold,
                int(data.enabled),
            ),
        )
        camera_id = cur.lastrowid
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    return _row_to_camera(row)


def update_camera(camera_id: int, data: CameraUpdate) -> Camera | None:
    fields = data.model_dump(exclude_unset=True)
    if not fields:
        return get_camera(camera_id)

    sets: list[str] = []
    values: list[object] = []
    for key, value in fields.items():
        if key == "roi":
            value = _roi_adapter.dump_json(data.roi).decode()
        elif key == "enabled":
            value = int(value)
        sets.append(f"{key} = ?")
        values.append(value)
    values.append(camera_id)

    with db.transaction() as conn:
        cur = conn.execute(
            f"UPDATE cameras SET {', '.join(sets)} WHERE id = ?", values
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM cameras WHERE id = ?", (camera_id,)).fetchone()
    return _row_to_camera(row)


def delete_camera(camera_id: int) -> bool:
    with db.transaction() as conn:
        cur = conn.execute("DELETE FROM cameras WHERE id = ?", (camera_id,))
    return cur.rowcount > 0
