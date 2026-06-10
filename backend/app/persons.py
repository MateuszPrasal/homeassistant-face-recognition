"""Repozytorium osób i embeddingów twarzy.

Embedding zapisujemy jako blob float32[512]. „Galeria" to spłaszczona lista
wszystkich embeddingów z nazwą osoby — używana przy dopasowaniu (matching.py).
"""

import sqlite3

import numpy as np

from . import db
from .schemas import Person


def _row_to_person(row: sqlite3.Row) -> Person:
    return Person(
        id=row["id"],
        name=row["name"],
        created_at=row["created_at"],
        face_count=row["face_count"] if "face_count" in row.keys() else 0,
    )


def list_persons() -> list[Person]:
    with db.transaction() as conn:
        rows = conn.execute(
            """
            SELECT p.*, COUNT(f.id) AS face_count
            FROM persons p LEFT JOIN faces f ON f.person_id = p.id
            GROUP BY p.id ORDER BY p.id
            """
        ).fetchall()
    return [_row_to_person(r) for r in rows]


def get_person(person_id: int) -> Person | None:
    with db.transaction() as conn:
        row = conn.execute(
            """
            SELECT p.*, COUNT(f.id) AS face_count
            FROM persons p LEFT JOIN faces f ON f.person_id = p.id
            WHERE p.id = ? GROUP BY p.id
            """,
            (person_id,),
        ).fetchone()
    return _row_to_person(row) if row else None


def create_person(name: str) -> Person:
    with db.transaction() as conn:
        cur = conn.execute("INSERT INTO persons (name) VALUES (?)", (name,))
        pid = cur.lastrowid
    return get_person(pid)  # type: ignore[return-value]


def delete_person(person_id: int) -> bool:
    with db.transaction() as conn:
        cur = conn.execute("DELETE FROM persons WHERE id = ?", (person_id,))
    return cur.rowcount > 0


def add_face(person_id: int, embedding: np.ndarray) -> int:
    blob = embedding.astype(np.float32).tobytes()
    with db.transaction() as conn:
        cur = conn.execute(
            "INSERT INTO faces (person_id, embedding) VALUES (?, ?)", (person_id, blob)
        )
        return int(cur.lastrowid)


def delete_face(face_id: int) -> bool:
    with db.transaction() as conn:
        cur = conn.execute("DELETE FROM faces WHERE id = ?", (face_id,))
    return cur.rowcount > 0


def load_gallery() -> list[tuple[int, str, np.ndarray]]:
    """Wszystkie embeddingi z nazwą osoby — (person_id, name, emb float32[512])."""
    with db.transaction() as conn:
        rows = conn.execute(
            """
            SELECT f.person_id, p.name, f.embedding
            FROM faces f JOIN persons p ON p.id = f.person_id
            """
        ).fetchall()
    return [
        (r["person_id"], r["name"], np.frombuffer(r["embedding"], dtype=np.float32))
        for r in rows
    ]
