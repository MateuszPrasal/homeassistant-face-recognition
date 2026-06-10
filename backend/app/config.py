"""Konfiguracja serwisu z zmiennych środowiskowych.

W add-onie HA OS opcje z `config.yaml` trafiają tu jako env (przez run.sh).
"""

import os
from pathlib import Path

# Korzeń backendu (katalog z app/, static/, models/).
BASE_DIR = Path(__file__).resolve().parent.parent

# Katalog ze statycznym frontem (export Next.js). W kontenerze: /app/static.
# Lokalnie domyślnie backend/static (wynik `npm run build:backend`).
STATIC_DIR = Path(os.getenv("FACE_STATIC_DIR", str(BASE_DIR / "static")))

# Katalog danych trwałych (SQLite, snapshoty). W add-onie: /data.
DATA_DIR = Path(os.getenv("FACE_DATA_DIR", str(BASE_DIR / "data")))

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

# Modele ONNX. Lokalnie domyślnie backend/models; w add-onie wskaż na /data/models
# (FACE_MODELS_DIR), żeby pobrane raz pliki przetrwały restart.
MODELS_DIR = Path(os.getenv("FACE_MODELS_DIR", str(BASE_DIR / "models")))

# Kaskada ML. Wyłączenie (FACE_ENABLE_CASCADE=0) zostawia samą Fazę 1 (gate ruchu).
ENABLE_CASCADE = os.getenv("FACE_ENABLE_CASCADE", "1") != "0"

# Progi kaskady (do strojenia na realnych danych).
PERSON_CONF = float(os.getenv("FACE_PERSON_CONF", "0.5"))  # pewność klasy person (SSD)
FACE_DET_THRESH = float(os.getenv("FACE_DET_THRESH", "0.4"))  # próg detekcji twarzy (SCRFD)
MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.4"))  # cosine: znany >= próg

# Katalog na snapshoty ALERT-ów (źródło zdjęcia dla MQTT w Fazie 4).
ALERTS_DIR = DATA_DIR / "alerts"
