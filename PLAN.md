# Plan wdrożenia

Plan fazami. Każda faza jest samodzielnie testowalna i kończy się czymś, co da
się odpalić i zobaczyć. Kontekst i decyzje: `CLAUDE.md`.

## Założenia (ustalone z userem)

- Sprzęt: Raspberry Pi 5 (4–8 GB), HA OS, wszystko na jednym RPi.
- Gotowe na HA OS: **go2rtc** i **Mosquitto**.
- Obraz: snapshot JPEG z go2rtc (źródło RTSP po stronie go2rtc).
- Kaskada dwóch modeli (onnxruntime, CPU, arm64): **lekki detektor osoby**
  (YOLOv8n / MobileNet-SSD, klasa `person`) → **InsightFace `buffalo_s`** (twarz
  + embedding 512-d).
- ROI **pierwszej klasy**: jeden zaznaczony fragment per kamera, na którym działa
  cała kaskada. Konfigurowalny od Fazy 1, rysowany w UI w Fazie 3.
- Logika zdarzeń: brak osoby → nic; osoba + znana twarz → OK; osoba + nieznana
  twarz → ALERT; osoba + brak twarzy → ALERT. ALERT = event + zdjęcie do HA.
- Wyzwalanie: snapshot co X s + gate ruchu w ROI (pre-filtr), cooldown.
- Kanał do HA: MQTT (discovery + encja `image`).
- UI: Next.js `output: 'export'`, serwowane przez FastAPI, pod Ingress.
- Kamery: projektujemy pod wiele, uruchamiamy jedną.

## Faza 0 — Szkielet repo i add-onu ✅ ZROBIONE

- [x] Struktura: `backend/` (FastAPI, py3.12/uv), `frontend/` (Next.js 16,
  output:export), manifest add-onu w korzeniu, `docs/`.
- [x] `Dockerfile` multi-stage: `node:24` build frontu → `python:3.12-slim`
  runtime. Zbudowany i uruchomiony, koła **aarch64** OK.
- [x] `config.yaml`: Ingress (port 8099), `mqtt:want`, `map: data:rw`.
- [x] Weryfikacja: backend lokalnie i w kontenerze serwuje statyczny front
  (`/api/health` OK, `/` 200, assety 200).
- Zostaje na Fazę 5: pełna obsługa prefiksu Ingress (wstrzyknięcie `<base href>`
  z `X-Ingress-Path`) — Next 16 generuje absolutne `/_next/...`. Opcje
  konfiguracyjne (kamera, próg, interwał) dochodzą wraz z funkcjami.

## Faza 1 — Akwizycja obrazu + ROI ✅ ZROBIONE

- [x] Klient snapshotów go2rtc (`snapshot.py`): `/api/frame.jpeg?src=<stream>`
  lub pełny URL snapshotu. Synchroniczny `httpx.Client` (używany w wątkach).
- [x] Pętla w tle (`worker.py`): wątek per kamera, co `interval_seconds` pobiera
  klatkę; `WorkerManager` start/stop/reload (mutacja konfiguracji = reload).
- [x] **ROI pierwszej klasy** (`roi.py`, kolumna `cameras.roi` jako JSON):
  znormalizowany prostokąt/wielokąt, dyskryminowana unia pydantic, domyślnie
  cały kadr. Ustawiany przez API (rysowanie w UI dopiero w Fazie 3).
- [x] Gate ruchu (`motion.py`): różnica klatek ograniczona do ROI (kadr do bboxu
  + maska wielokąta, OpenCV), frakcja zmienionych pikseli vs `motion_threshold`.
- [x] Konfiguracja kamery w SQLite (`db.py`, `cameras.py`) + API CRUD
  (`routes.py`): `/api/cameras`, `/api/cameras/{id}` (GET/PATCH/DELETE),
  `/api/cameras/{id}/snapshot` (podgląd), `/api/status` (ruch/brak per kamera).
- [x] Testy `pytest` (gate ruchu, ROI rect/poly, CRUD, walidacja). Weryfikacja
  integracyjna: lokalny serwer JPEG → w logach „RUCH / brak ruchu".
- Cel fazy osiągnięty: w logach widać „ruch / brak ruchu" w ROI; bez modeli ML.
- Dług: `motion_threshold` to próg startowy (0.02) — strojenie na realnym
  obrazie. Brak debounce/min. liczby klatek ruchu (dojdzie z cooldownem w Fazie 2).

## Faza 2 — Kaskada osoba → twarz + rozpoznawanie

- Detektor osoby (YOLOv8n / MobileNet-SSD, ONNX), klasa `person`, w obrębie ROI.
- Wczytanie `buffalo_s` (onnxruntime): detekcja twarzy na obszarze osoby +
  embedding 512-d.
- Schemat `persons` / `faces`, zapis embeddingów (blob float32).
- Dopasowanie cosine do bazy, konfigurowalny próg, wynik znany/nieznany + score.
- Spięcie kaskady z pętlą: gate ruchu → osoba → twarz → embedding → dopasowanie,
  z wyznaczeniem `outcome` (`ok` / `unknown_face` / `person_no_face`).
- Cooldown po ALERT-cie.
- Cel fazy: w logach pojawia się outcome: „znany: <imię> (score)" / „nieznany
  (score)" / „osoba bez twarzy".

## Faza 3 — UI (zarządzanie twarzami + ROI)

- Next.js (export) serwowane przez FastAPI; ścieżki względne pod Ingress.
- Ekrany: lista osób, dodanie osoby + wgranie/zrobienie zdjęcia (podgląd
  wykrytej twarzy przed zapisem), podgląd kadru z kamery, **rysowanie ROI** na
  podglądzie (zapis do `cameras.roi`).
- Endpointy API pod te akcje; zapis embeddingu przy dodawaniu twarzy.
- Cel fazy: pełny obieg „dodaj osobę ze zdjęcia → ląduje w bazie → rozpoznawana"
  oraz „narysuj ROI → kaskada liczy się tylko w nim".

## Faza 4 — Integracja MQTT + powiadomienia HA

- Klient MQTT, discovery encji: `image` (snapshot ALERT-u), `event`/`sensor`
  (ostatnie rozpoznanie z polem `outcome`), opcjonalnie `binary_sensor`.
- Publikacja przy ALERT-cie (`unknown_face` **lub** `person_no_face`): zdjęcie +
  metadane (outcome, score, kamera, czas).
- Przykładowa automatyzacja HA (`docs/`): wyzwalacz → `notify` ze zdjęciem (treść
  pusha zależna od outcome: „nieznana osoba" vs „osoba bez widocznej twarzy").
- Cel fazy: oba typy ALERT-u przed kamerą → push na telefon ze zdjęciem.

## Faza 5 — Pakowanie i hardening add-onu

- Dopięcie `config.yaml`/`build.yaml`, opcje konfiguracyjne, walidacja.
- Trwałość SQLite i modeli w katalogu danych add-onu.
- Obsługa restartów, błędów go2rtc/MQTT, sensowne logi.
- Cel fazy: instalacja „od zera" na czystym HA OS działa powtarzalnie.

## Faza 6 — Wiele kamer i strojenie

- Wiele kamer: lista w bazie, pętla per kamera, wspólny budżet inferencji.
- Strojenie progu cosine na realnych danych, log `detections` do analizy.
- Opcjonalnie: drugi wyzwalacz z `binary_sensor` ruchu HA (szybsza reakcja).

## Otwarte kwestie (do potwierdzenia w trakcie)

- Wybór detektora osoby (YOLOv8n vs MobileNet-SSD) + próg pewności klasy `person`.
- Próg cosine — wartość startowa i sposób strojenia (UI? config?).
- `person_no_face`: osobny, dłuższy cooldown / minimalny czas obecności, żeby
  znajomy stojący chwilę tyłem nie generował lawiny alertów „osoba bez twarzy".
- Czy logować wszystkie detekcje (`detections`), czy tylko zdarzenia.
- Polityka retencji zdjęć nieznanych twarzy (ile trzymać, gdzie).
- Pełny serwer Next (SSR) vs export statyczny — domyślnie export; zmiana tylko
  jeśli pojawi się realna potrzeba SSR.
