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

# Bazowy adres API go2rtc. W HA OS go2rtc to osobny add-on; domyślnie API na 1984.
# Źródło kamery, które nie jest pełnym URL-em, traktujemy jako nazwę streamu go2rtc
# i składamy: {GO2RTC_URL}/api/frame.jpeg?src=<źródło>.
GO2RTC_URL = os.getenv("FACE_GO2RTC_URL", "http://localhost:1984").rstrip("/")

# Timeout pobrania pojedynczego snapshotu (s).
SNAPSHOT_TIMEOUT = float(os.getenv("FACE_SNAPSHOT_TIMEOUT", "5"))

# Plik bazy SQLite w katalogu danych (trwałość między restartami add-onu).
DB_PATH = DATA_DIR / "face.sqlite"
