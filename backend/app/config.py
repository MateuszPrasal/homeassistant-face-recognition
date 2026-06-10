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

# Poziom logowania (opcja add-onu log_level → FACE_LOG_LEVEL). DEBUG/INFO/WARNING/ERROR.
LOG_LEVEL = os.getenv("FACE_LOG_LEVEL", "info").upper()

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

# Wiele kamer = wiele wątków pętli. Inferencja kaskady (dwa modele ONNX na CPU)
# jest kosztowna — równoległe odpalenia na RPi się duszą. Współdzielony semafor
# serializuje inferencję (domyślnie 1 naraz); zwiększ tylko na mocniejszym CPU.
INFERENCE_CONCURRENCY = max(1, int(os.getenv("FACE_INFERENCE_CONCURRENCY", "1")))

# Log detekcji (do strojenia progu cosine). Przycinany do ostatnich N wpisów.
MAX_DETECTIONS = max(0, int(os.getenv("FACE_MAX_DETECTIONS", "1000")))

# CORS — pod Ingress front i API są tym samym originem, więc domyślnie pusto.
# Pod dev (Next na :3000, backend na :8099) ustaw FACE_CORS_ORIGINS=http://localhost:3000.
CORS_ORIGINS = [o.strip() for o in os.getenv("FACE_CORS_ORIGINS", "").split(",") if o.strip()]

# --- MQTT (Faza 4) ---
# W add-onie dane brokera podaje Supervisor (services: mqtt:want) — pobieramy je
# z http://supervisor/services/mqtt po SUPERVISOR_TOKEN. Lokalnie/dev: jawne env.
# Kolejność: jeśli FACE_MQTT_HOST ustawiony → bierzemy env; inaczej → Supervisor.
MQTT_ENABLE = os.getenv("FACE_MQTT_ENABLE", "1") != "0"
MQTT_HOST = os.getenv("FACE_MQTT_HOST") or None
MQTT_PORT = int(os.getenv("FACE_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("FACE_MQTT_USERNAME") or None
MQTT_PASSWORD = os.getenv("FACE_MQTT_PASSWORD") or None
MQTT_SSL = os.getenv("FACE_MQTT_SSL", "0") == "1"
# Prefiks tematów stanu serwisu i prefiks MQTT discovery HA.
MQTT_BASE_TOPIC = os.getenv("FACE_MQTT_BASE_TOPIC", "face_recognition")
MQTT_DISCOVERY_PREFIX = os.getenv("FACE_MQTT_DISCOVERY_PREFIX", "homeassistant")
# Token Supervisora (ustawiany w add-onie HA OS); poza add-onem brak.
SUPERVISOR_TOKEN = os.getenv("SUPERVISOR_TOKEN") or None
