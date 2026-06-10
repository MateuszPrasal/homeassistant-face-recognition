# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Status: projekt na etapie startu (greenfield). Poniższe opisuje **uzgodnioną
> architekturę docelową**, a nie istniejący kod. W miarę powstawania kodu
> aktualizuj sekcje „Komendy" i „Struktura" realnymi wartościami. Plan wdrożenia
> fazami: `PLAN.md`.

## Czym jest ten projekt

Rozpoznawanie twarzy spięte z Home Assistant. **Osobny serwis** (kontener
Docker, pakowany jako **add-on HA OS**) bierze obraz z kamery IP, sprawdza na
wyznaczonym fragmencie kadru, czy widoczna twarz należy do zarejestrowanego
domownika. Twarz nieznana → przez MQTT leci zdarzenie + zdjęcie do Home
Assistant, a automatyzacja wysyła push na telefony domowników.

Użytkownik zarządza twarzami z poziomu UI serwisu (osadzonego w panelu HA przez
Ingress): dodaje osobę, wgrywa/robi zdjęcie, model wykrywa twarz, liczy wektor
(embedding) i zapisuje do bazy.

## Kluczowe decyzje architektoniczne

To są świadome wybory — trzymaj się ich, dopóki user ich nie zmieni. „Dlaczego"
jest istotne, bo każda z tych rzeczy ma kuszącą, ale gorszą alternatywę.

- **Dwie części, nie „integracja" w sensie custom component.** Serwis to osobny
  kontener z własnym API/UI/bazą. Z Home Assistant rozmawia tylko przez MQTT.
  Nie ładujemy kodu do wnętrza HA.
- **Pakowanie: add-on HA OS z Ingress.** UI „wmontowane w HA" realizujemy przez
  Ingress (pozycja w panelu bocznym, bez osobnego logowania), nie przez
  `panel_custom`/iframe z zewnętrznym URL.
- **Sprzęt: Raspberry Pi 5 (4–8 GB), wszystko na jednym RPi obok HA.** To
  ogranicza budżet CPU/RAM — patrz „Wydajność".
- **Dwa modele, kaskadowo: osoba → twarz.** Najpierw **lekki detektor osoby**
  (**MobileNet-SSD v1**, klasa `person`, ONNX) w ROI. Dopiero gdy jest osoba —
  modele z **`buffalo_s` na samym onnxruntime** (`det_500m` SCRFD + `w600k_mbf`
  ArcFace) na obszarze osoby. Twarz → embedding 512-d → **cosine similarity** do
  bazy. Świadome wybory:
  - **MobileNet-SSD, nie YOLOv8n** — YOLOv8 jest na AGPL, a `yolov8n.onnx` nie da
    się czysto pozyskać (eksport przez torcha / auth HF). MobileNet-SSD ma
    permisywną licencję i pobiera się wprost. Detektor siedzi za interfejsem
    (`app/ml/person.py`) — podmiana możliwa, gdy ktoś zaakceptuje AGPL.
  - **Surowy onnxruntime, nie pakiet `insightface`** — pakiet ciągnie
    scikit-image/scipy/tifffile i kompilację cython. Bierzemy z `buffalo_s.zip`
    tylko dwa pliki ONNX i obsługujemy je sami. **Bez torcha.**
  - Świadomie NIE używamy `face_recognition`/dlib (gorsza dokładność + ból
    kompilacji na ARM).
- **ROI to byt pierwszej klasy.** Jeden zaznaczony fragment kadru, na którym
  działa cała kaskada (osoba → twarz). Konfigurowalny od początku (config/baza),
  rysowany w UI w Fazie 3. Każda kamera ma swój ROI. Kadrujemy do ROI **przed**
  detekcją — mniej CPU, mniej fałszywek.
- **Reakcja zależy od wyniku kaskady** (kluczowa logika produktu):
  - brak osoby → nic;
  - osoba + **znana** twarz → OK (log, bez powiadomienia);
  - osoba + **nieznana** twarz → ALERT (event + zdjęcie);
  - osoba + **brak** twarzy (tyłem, zasłonięta) → ALERT (event + zdjęcie).
- **Wyzwalanie: snapshot co X s + tani gate ruchu jako pre-filtr.** Serwis co X
  sekund (start: 2–3 s) pobiera JPEG **z go2rtc** (`/api/frame.jpeg`), robi tani
  test ruchu w ROI (różnica klatek, OpenCV) i **dopiero przy zmianie** odpala
  kaskadę osoba→twarz. Gate ruchu chroni droższy detektor osoby przed odpalaniem
  na każdej klatce. Po trafieniu **cooldown** (30–60 s), żeby nie spamować.
  go2rtc dekoduje RTSP — serwis nie trzyma otwartego strumienia.
- **Baza: SQLite + numpy.** Skala domowa (kilka osób, kilkadziesiąt
  embeddingów). Porównanie wektorów brute-force w numpy. Żaden vector-DB nie
  jest potrzebny.
- **Zdjęcie w powiadomieniu: encja MQTT `image`.** Serwis publikuje snapshot
  nieznanej twarzy jako encję `image` (MQTT discovery); automatyzacja w HA
  dokłada to zdjęcie do pusha. Bez kombinowania z zewnętrznymi URL-ami.
- **Frontend: Next.js (React) w trybie `output: 'export'`** — statyczny build
  serwowany przez FastAPI. Bez runtime Node w produkcji (RAM na RPi). Ścieżki
  assetów **względne**, bo Ingress serwuje pod dynamicznym prefiksem
  `/api/hassio_ingress/<token>/` (absolutne ścieżki się z tym gryzą — to częsta
  pułapka).
- **Wielokamerowość w modelu danych od początku, uruchamiamy jedną.** Schemat i
  pętla projektowane pod wiele kamer; na start aktywna jedna.

## Architektura runtime

```
Kamera IP --RTSP--> go2rtc --snapshot JPEG--> [Add-on: FastAPI + Next(static) + ML loop + SQLite]
                                                     |
                kadr ROI → gate ruchu → detektor OSOBY → detektor TWARZY → embedding → cosine
                                                     |  ALERT (nieznana twarz / osoba bez twarzy)
                                                     |  → MQTT discovery + encja image
                                                     v
                                              Mosquitto --> Home Assistant --> notify (push)
```

Jeden kontener (add-on) zawiera:
- **FastAPI** — REST API + serwowanie statycznego frontu. Endpoint pod Ingress.
- **Worker ML** — pętla akwizycji w tle (osobny wątek/zadanie asyncio; onnxruntime
  zwalnia GIL na czas inferencji). Kaskada:
  `snapshot → gate ruchu (ROI) → detektor osoby (ROI) → detektor twarzy (na obszarze osoby) → embedding → dopasowanie`.
  Reakcja wg tabeli wyników (znana twarz = OK; nieznana twarz / brak twarzy przy
  wykrytej osobie = ALERT → publikacja MQTT ze zdjęciem).
- **Klient MQTT** — discovery encji na starcie, publikacja zdarzeń i zdjęć.
- **SQLite** — w katalogu danych add-onu (trwałość między restartami).

## Model danych (SQLite, docelowo)

- `cameras` — id, nazwa, źródło (nazwa streamu go2rtc / URL snapshotu), `roi`
  (znormalizowany wielokąt/prostokąt jako JSON), `interval_seconds`,
  `cooldown_seconds`, `enabled`.
- `persons` — id, nazwa, utworzono.
- `faces` — id, person_id, `embedding` (blob float32[512]), miniatura, źródłowe
  zdjęcie, utworzono. (Jedna osoba może mieć wiele embeddingów — różne ujęcia.)
- `detections` (log, opcjonalnie) — id, camera_id, czas, `person_detected` (bool),
  `face_detected` (bool), matched_person_id (nullable), score,
  `outcome` (`ok` | `unknown_face` | `person_no_face`), ścieżka snapshotu.

ROI to znormalizowany wielokąt/prostokąt per kamera (kolumna `roi` w `cameras`).
Jest pierwszej klasy: konfigurowalny od Fazy 1 (najpierw przez config/API),
rysowany w UI w Fazie 3. Cała kaskada (osoba→twarz) liczy się **wyłącznie**
wewnątrz ROI.

Dopasowanie: cosine similarity nowego embeddingu do wszystkich w `faces`, bierz
max; `>= próg` → znany; inaczej → nieznany. Próg dla ArcFace/cosine ~0.35–0.5 —
do strojenia na realnych danych, wystawić jako konfigurowalny.

## Encje MQTT (discovery)

- `image` — ostatni snapshot ALERT-u (źródło zdjęcia do pusha).
- `event` / `sensor` — ostatnie rozpoznanie z polem `outcome`
  (`ok` / `unknown_face` / `person_no_face`), nazwa (jeśli znana), score.
- opcjonalnie `binary_sensor` — „obecny ktoś niezweryfikowany" (nieznana twarz
  lub osoba bez twarzy).

Powiadomienie składa user w automatyzacji HA (wyzwalacz = zdarzenie/encja,
akcja = `notify` ze zdjęciem). W repo trzymamy przykładowy YAML automatyzacji.

## Wydajność (RPi 5 — twarde ograniczenia)

- Kaskada odpala się **tylko na ruch w ROI**, nie na każdą klatkę. To jest cały
  sens gate'u — bez niego dwa modele na RPi się duszą.
- Detektor twarzy odpala się **tylko gdy detektor osoby coś znalazł** — drugi
  poziom oszczędności. Brak osoby = nie ruszamy `buffalo_s`.
- Budżet na klatkę (RPi 5, CPU): detektor osoby ~0,2–0,5 s + `buffalo_s`
  ~0,3–0,8 s. Sumują się tylko, gdy jest osoba. Interwał snapshotu dobierz tak,
  by inferencje się nie nakładały.
- Kadruj do ROI **przed** detekcją osoby; detektor twarzy puszczaj na obszarze
  osoby, nie na całym ROI — mniej pikseli, mniej CPU, mniej fałszywek.
- Wiele kamer = wiele pętli = liniowo więcej CPU. Przy dokładaniu kamer pilnuj
  sumarycznego budżetu (rozważ wspólną kolejkę inferencji zamiast N równoległych).
- Awaryjnie, gdy za wolno: akcelerator Hailo (RPi 5 AI Kit) albo przeniesienie
  serwisu na mocniejszy sprzęt (model danych to dopuszcza).

## Komendy

Wersje: **Python 3.12** (backend), **Node 24** + **Next.js 16** (frontend).

```bash
# Backend (z katalogu backend/)
uv venv --python 3.12          # utworzenie venv
uv sync                        # instalacja zależności (z pyproject)
uv run uvicorn app.main:app --reload --port 8099   # dev
uv run pytest                  # testy (gate ruchu, ROI, API kamer)

# Frontend (z katalogu frontend/, Node 24 przez nvm)
npm install
npm run dev                    # tryb dev Next
npm run build:backend          # export statyczny → backend/static (serwowany przez FastAPI)

# Obraz add-onu (z korzenia repo) — multi-stage, arm64 + amd64
docker build -t face-recognition:dev .
docker run --rm -p 8099:8099 face-recognition:dev   # health: /api/health
```

Backend serwuje statyczny front spod `STATIC_DIR` (env `FACE_STATIC_DIR`,
domyślnie `backend/static`; w kontenerze `/app/static`).

Env runtime:
- `FACE_DATA_DIR` — SQLite + dane (snapshoty ALERT-ów w `data/alerts`), w add-onie `/data`.
- `FACE_PORT` (8099), `FACE_GO2RTC_URL` (baza API go2rtc, `http://localhost:1984`),
  `FACE_SNAPSHOT_TIMEOUT` (s).
- `FACE_MODELS_DIR` — katalog modeli ONNX (lokalnie `backend/models`, w add-onie
  `/data/models`). Modele dociągają się przy pierwszym starcie.
- `FACE_ENABLE_CASCADE` (`1`/`0`) — wyłącza kaskadę ML (testy/CI lecą z `0`,
  bez pobierania modeli).
- Progi kaskady: `FACE_PERSON_CONF` (0.5), `FACE_DET_THRESH` (0.4 — detektor twarzy),
  `FACE_MATCH_THRESHOLD` (0.4 — cosine do galerii; ~0.35–0.5 do strojenia).

## Frontend: Next.js 16 — czytaj dokumentację z paczki

`create-next-app` wstawił `frontend/AGENTS.md` (i `CLAUDE.md` → `@AGENTS.md`) z
twardą regułą: **Next 16 ma zmiany łamiące względem wiedzy treningowej — przed
pisaniem kodu Next czytaj `node_modules/next/dist/docs/`**. Stosuj się do tego.
Ustalone empirycznie: export wrzuca **absolutne** ścieżki `/_next/...` — pod
Ingress wymaga to wstrzyknięcia `<base href>` z `X-Ingress-Path` (Faza 5).

## Struktura repo

Korzeń repo = katalog add-onu (kontekst buildu Dockera widzi `backend/` i `frontend/`).

```
backend/    FastAPI (app/), pyproject (uv, py3.12), venv w .venv, statyk w static/
            app/: main (lifespan+routery+budowa kaskady), routes (API kamer),
            routes_persons (API osób + enrollment twarzy), cameras (CRUD),
            persons (repo osób/twarzy + galeria), db (SQLite), schemas,
            roi (model+maska), snapshot (go2rtc), motion (gate ruchu),
            matching (cosine brute-force), cascade (osoba→twarz→embedding→match),
            worker (pętle akwizycji + cooldown + zapis ALERT-ów);
            app/ml/: models (pobieranie/ścieżki ONNX), person (MobileNet-SSD),
            face (SCRFD det_500m), recognize (ArcFace w600k_mbf), __init__ (roi_crop);
            tests/ (pytest, conftest = fixture client z kaskadą off)
frontend/   Next.js 16 (App Router, Tailwind), output:'export' → build:backend
docs/        przykłady (automatyzacje HA — dojdą w Fazie 4)
config.yaml  manifest add-onu (Ingress, port 8099, mqtt:want, map data)
build.yaml   obraz bazowy per arch (python:3.12-slim)
Dockerfile   multi-stage: node:24 (build frontu) → python:3.12-slim (runtime)
run.sh       start: uvicorn na 0.0.0.0:$FACE_PORT
```

## Pułapki specyficzne dla tego projektu

- **Ingress + ścieżki absolutne** — patrz wyżej. Wszystko (assety, wywołania API
  z frontu) liczone względem bazowej ścieżki podawanej przez Ingress, nie od `/`.
- **arm64** — onnxruntime, opencv i modele muszą mieć działające koła/buildy na
  aarch64. Sprawdzaj to przy każdej zależności, nie zakładaj.
- **go2rtc jako źródło klatek** — nie otwieraj RTSP samodzielnie, jeśli go2rtc
  już to robi. Pobieraj snapshot z jego API.
- **Cooldown i debounce** — bez nich jeden gość w kadrze = lawina powiadomień.
