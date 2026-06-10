"""Konfiguracja serwisu z zmiennych środowiskowych.

W add-onie HA OS opcje z `config.yaml` trafiają tu jako env (przez run.sh).
"""

import os
from pathlib import Path

# Katalog ze statycznym frontem (export Next.js). W kontenerze: /app/static.
# Lokalnie domyślnie backend/static (wynik `npm run build:backend`).
STATIC_DIR = Path(
    os.getenv("FACE_STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static"))
)

# Katalog danych trwałych (SQLite, snapshoty). W add-onie: /data.
DATA_DIR = Path(os.getenv("FACE_DATA_DIR", str(Path(__file__).resolve().parent.parent / "data")))

# Port nasłuchu (Ingress kieruje na ten port wewnątrz kontenera).
PORT = int(os.getenv("FACE_PORT", "8099"))
