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

## Faza 2 — Kaskada osoba → twarz + rozpoznawanie ✅ ZROBIONE

- [x] Detektor osoby: **MobileNet-SSD v1** (ONNX, onnxruntime), klasa person=1,
  NMS w grafie. Wybór: permisywna licencja + bezpośrednio pobieralny, w odróżnieniu
  od YOLOv8n (AGPL, eksport przez torcha). Za interfejsem `app/ml/person.py` —
  podmiana na YOLOv8n możliwa, gdy ktoś zaakceptuje AGPL. **Bez torcha.**
- [x] Twarz z **buffalo_s na samym onnxruntime** (bez pakietu insightface — ciągnął
  scikit-image/scipy i kompilację cython): `det_500m` (SCRFD, `app/ml/face.py` —
  dekoder 3 stridy + NMS + 5 landmarków) → `w600k_mbf` (ArcFace, `app/ml/recognize.py`
  — align 5-pkt do 112×112, embedding 512-d L2-norm).
- [x] Schemat `persons` / `faces` (embedding blob float32[512]), repo `app/persons.py`,
  galeria do dopasowania. Matching cosine brute-force numpy (`app/matching.py`),
  próg `FACE_MATCH_THRESHOLD` (start 0.4).
- [x] Kaskada `app/cascade.py`: ROI → osoba → (na obszarze osoby) twarz → embedding
  → dopasowanie → `outcome`. Priorytet: `unknown_face` > `person_no_face` > `ok`.
- [x] Spięcie z workerem: po gate ruchu odpala kaskadę; ALERT zapisuje snapshot do
  `/data/alerts` i ma **cooldown** (`cooldown_seconds`). Modele ładowane raz,
  współdzielone między kamerami (onnxruntime.Run jest thread-safe).
- [x] API osób + enrollment twarzy ze zdjęcia (`app/routes_persons.py`):
  `POST /api/persons/{id}/faces` wykrywa twarz, liczy embedding, zapisuje.
- [x] Testy: logika outcome'ów (atrapy), matching cosine, API osób; test
  integracyjny na realnych modelach za flagą `FACE_IT=1`. Weryfikacja: enroll
  Obamy → `obama→ok`, `biden→unknown_face`, cross-photo match 0.54.
- Cel fazy osiągnięty: w logach outcome „OK — <imię> (score)" / „ALERT unknown_face"
  / „ALERT person_no_face", snapshoty ALERT-ów na dysku, cooldown działa.

## Faza 3 — UI (zarządzanie twarzami + ROI) ✅ ZROBIONE

- [x] Next.js 16 (export) serwowany przez FastAPI. **Jedna trasa + zakładki**
  (stan React, bez routingu klienta) — omija pułapkę Ingress z absolutnymi
  ścieżkami `next/link` do czasu Fazy 5. Klient API (`lib/api.ts`) bije w ścieżki
  **względne** (`api/...`), pod dev przez `NEXT_PUBLIC_API_BASE`.
- [x] Ekran **Osoby**: lista z liczbą twarzy, dodawanie osoby, karta osoby z listą
  twarzy (usuwanie pojedynczych), usuwanie osoby. Enrollment: wybór pliku →
  `POST /api/detect` → **podgląd wykrytej twarzy** (ramka SVG, zielona = 1 twarz,
  czerwona = 0/wiele) → zapis przez `POST /api/persons/{id}/faces`. Zapis tylko
  przy dokładnie jednej twarzy; obsługa 503 (kaskada off).
- [x] Ekran **Kamery**: dodawanie/lista/usuwanie, edytowalne ustawienia (źródło,
  interwał, cooldown, próg ruchu, enabled), podgląd snapshotu z `/api/cameras/{id}/snapshot`
  (fallback, gdy go2rtc niedostępny — 502).
- [x] **Edytor ROI** (`RoiEditor`, canvas/SVG na podglądzie): prostokąt
  przeciąganiem, wielokąt klikaniem (≥3 wierzchołki), „cały kadr", zapis do
  `cameras.roi` przez PATCH. Współrzędne znormalizowane 0..1 (overlay `viewBox 0 0 1 1`).
- [x] Endpointy pod UI: `GET /api/persons/{id}/faces`, `POST /api/detect`
  (detekcja bez zapisu), CORS pod dev (`FACE_CORS_ORIGINS`). Testy backendu (25).
- [x] Weryfikacja: build statyczny → FastAPI serwuje front na `/`; na realnych
  modelach `/detect` (obama 1 twarz / two_people 2 twarze) i enroll (422 przy 2)
  działają end-to-end.
- Cel fazy osiągnięty: pełny obieg „dodaj osobę ze zdjęcia → baza → rozpoznawana"
  i „narysuj ROI → zapis per kamera".
- Dług: „zrobić zdjęcie" z kamerki (getUserMedia) odłożone — upload pliku domyka
  obieg. Pełny Ingress (base href + absolutne `/_next/...`) nadal na Fazę 5.

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
