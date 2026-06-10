"""Warstwa SQLite.

Skala domowa — jedno współdzielone połączenie chronione blokadą wystarcza.
Połączenie jest `check_same_thread=False`, bo dotyka go zarówno pętla eventów
FastAPI (endpointy sync w threadpoolu), jak i wątki workerów akwizycji.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager

from .config import DATA_DIR, DB_PATH

# Schemat. ROI trzymamy jako JSON (znormalizowany prostokąt/wielokąt) — patrz roi.py.
# Wielokamerowość od początku: każda kamera ma własne źródło, ROI i interwał.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS cameras (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    source           TEXT    NOT NULL,
    roi              TEXT    NOT NULL,
    interval_seconds REAL    NOT NULL DEFAULT 3.0,
    cooldown_seconds REAL    NOT NULL DEFAULT 45.0,
    motion_threshold REAL    NOT NULL DEFAULT 0.02,
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Osoby (domownicy) i ich embeddingi twarzy. Jedna osoba może mieć wiele
-- embeddingów (różne ujęcia) — patrz `faces`. Embedding to float32[512] jako blob.
CREATE TABLE IF NOT EXISTS persons (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS faces (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    embedding  BLOB    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_faces_person ON faces(person_id);

-- Log detekcji (Faza 6) — do strojenia progu cosine i podglądu „co widziała
-- kamera". Wpisywany przy każdej wykrytej osobie (outcome != none). Przycinany
-- do ostatnich N (FACE_MAX_DETECTIONS). matched_person_id nullable (gdy nieznany
-- / brak twarzy); snapshot_path tylko dla zapisanych ALERT-ów.
CREATE TABLE IF NOT EXISTS detections (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id         INTEGER NOT NULL,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    person_detected   INTEGER NOT NULL,
    face_detected     INTEGER NOT NULL,
    matched_person_id INTEGER REFERENCES persons(id) ON DELETE SET NULL,
    matched_name      TEXT,
    score             REAL    NOT NULL DEFAULT 0.0,
    outcome           TEXT    NOT NULL,
    snapshot_path     TEXT
);
CREATE INDEX IF NOT EXISTS idx_detections_id ON detections(id DESC);
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def init_db() -> None:
    """Tworzy plik bazy (jeśli brak) i schemat. Wołane raz na starcie."""
    global _conn
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute("PRAGMA foreign_keys=ON")
    _conn.executescript(_SCHEMA)
    _conn.commit()


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Dostęp do połączenia pod blokadą. Commit na wyjściu, rollback przy błędzie."""
    if _conn is None:
        raise RuntimeError("Baza nie zainicjalizowana — wywołaj init_db() na starcie.")
    with _lock:
        try:
            yield _conn
            _conn.commit()
        except Exception:
            _conn.rollback()
            raise


def close_db() -> None:
    """Zamyka połączenie (zamknięcie aplikacji)."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
