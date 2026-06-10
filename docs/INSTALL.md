# Instalacja add-onu w Home Assistant

Add-on jedzie tylko na **Home Assistant OS** (albo Supervised) — bo korzysta z
Supervisora (Ingress w panelu bocznym, dane brokera MQTT, trwały katalog `data`).
Na „Home Assistant Container" (samo `docker run` z core) add-onów nie ma — tam
odpalasz obraz ręcznie (sekcja na końcu).

Sprzęt docelowy: **Raspberry Pi 5** (`aarch64`). Do testów na PC działa `amd64`.

## Zanim zaczniesz — zależności

Add-on sam z siebie nie wystarczy, dogaduje się z trzema rzeczami:

1. **Broker MQTT** — add-on **Mosquitto broker** + integracja **MQTT**.
   Przez niego lecą zdarzenia i zdjęcia do HA. Supervisor poda add-onowi dane
   brokera automatycznie (`mqtt:want` w manifeście) — nic nie wpisujesz ręcznie.
2. **go2rtc** — to on dekoduje RTSP z kamery i daje add-onowi snapshot JPEG.
   Może być add-on **go2rtc**, albo go2rtc z **Frigate**, albo standalone.
   Add-on pobiera klatki z jego API (domyślnie `http://localhost:1984` — **zmień**
   na realny adres, patrz „Opcje" niżej).
3. **Kamera IP** z dostępnym strumieniem RTSP, dodana jako stream w go2rtc.

## Metoda A — przez repozytorium GitHub (zalecana)

Najprościej, gdy kod jest wypchnięty na GitHub.

1. W HA: **Ustawienia → Dodatki → Sklep z dodatkami**.
2. Menu (⋮ w prawym górnym rogu) → **Repozytoria**.
3. Wklej URL repo:
   `https://github.com/mprasal/homeassistant-face-recognition`
   i kliknij **Dodaj**.
4. Odśwież stronę. Na dole sklepu pojawi się sekcja **Rozpoznawanie twarzy** —
   wejdź i kliknij **Zainstaluj**.

Supervisor zbuduje obraz na urządzeniu (Dockerfile z korzenia repo, dla `aarch64`).
Pierwszy build trwa kilka minut.

## Metoda B — lokalny add-on (bez GitHuba, prosto z dysku)

Gdy chcesz wgrać kod ręcznie (np. wersja niewypchnięta).

1. Włącz dostęp do share `addons` — najprościej add-on **Samba share** albo
   **Advanced SSH & Web Terminal**.
2. Skopiuj **całą zawartość repo** (korzeń = katalog add-onu; `config.yaml` musi
   leżeć bezpośrednio w środku) do nowego folderu:
   ```
   /addons/face_recognition/
   ├── config.yaml
   ├── build.yaml
   ├── Dockerfile
   ├── run.sh
   ├── backend/
   └── frontend/
   ```
3. W HA: **Ustawienia → Dodatki → Sklep z dodatkami**, menu (⋮) → **Sprawdź
   aktualizacje**. W sekcji **Local add-ons** pojawi się **Rozpoznawanie twarzy**.
4. Wejdź i kliknij **Zainstaluj** (build jak wyżej).

> Po każdej zmianie kodu w `/addons/...` zrób **Przebuduj** na karcie add-onu,
> żeby Supervisor zbudował obraz od nowa.

## Konfiguracja i start

1. Na karcie add-onu → zakładka **Konfiguracja**. Pokrętła globalne
   (reszta — kamery, ROI — siedzi w UI add-onu, nie tutaj):

   | Opcja | Domyślnie | Po co |
   |---|---|---|
   | `go2rtc_url` | `http://localhost:1984` | **Adres API go2rtc.** `localhost` celuje w sam add-on — wpisz realny host, np. `http://a0d7b954-go2rtc:1984` (add-on go2rtc) albo IP:port maszyny z go2rtc. |
   | `match_threshold` | `0.4` | Próg cosine: powyżej = znana twarz. Strój na realnych danych (~0.35–0.5). |
   | `person_conf` | `0.5` | Próg pewności detektora osoby. |
   | `det_thresh` | `0.4` | Próg detektora twarzy. |
   | `snapshot_timeout` | `5.0` | Timeout pobrania klatki z go2rtc (s). |
   | `log_level` | `info` | `debug` przy diagnozie. |

2. Zakładka **Informacje**: włącz **Start przy starcie** i **Watchdog**
   (opcjonalnie), kliknij **Uruchom**.
3. Pierwszy start **dociąga modele ONNX** do `/data/models` (kilkadziesiąt MB) —
   w logach add-onu zobaczysz pobieranie. Kolejne starty są szybkie.
4. W panelu bocznym HA pojawi się pozycja **Twarze** (Ingress, bez osobnego
   logowania). Otwórz ją — to UI add-onu.

## Pierwsze użycie (w UI „Twarze")

1. **Osoby** → dodaj domownika → wgraj zdjęcie twarzy. Model wykryje twarz
   (zielona ramka = OK, jedna twarz), policzy embedding i zapisze.
2. **Kamery** → dodaj kamerę (nazwa + nazwa streamu go2rtc / URL snapshotu) →
   rozwiń → narysuj **ROI** (fragment kadru, na którym liczy się detekcja) →
   ustaw interwał i cooldown → zapisz.
3. **Zdarzenia** — log detekcji (do strojenia progu). Wpis przy każdej wykrytej
   osobie, niezależnie od cooldownu.

## Powiadomienia (push ze zdjęciem)

Add-on publikuje przez MQTT (discovery) jedno urządzenie HA z encjami per kamera:
`sensor` (stan = wynik: `ok` / `unknown_face` / `person_no_face`),
`binary_sensor` (occupancy) i `image` (ostatni snapshot alertu).

Push składasz **automatyzacją w HA**: wyzwalacz = zmiana sensora `outcome` na
`unknown_face` / `person_no_face`, akcja = `notify` ze zdjęciem z encji `image`.
Gotowy przykład: [`automation.yaml`](automation.yaml).

## Aktualizacja

- **Metoda A:** podbij `version` w `config.yaml`, wypchnij na GitHub → na karcie
  add-onu pojawi się **Aktualizuj**.
- **Metoda B:** podmień pliki w `/addons/face_recognition/` → **Przebuduj**.

## Bez Home Assistant OS (czysty Docker)

Gdy nie masz Supervisora (HA Container / test na PC) — bez Ingressu i bez
auto-konfiguracji MQTT, wszystko przez env:

```bash
docker build -t face-recognition:dev .
docker run --rm -p 8099:8099 \
  -v "$PWD/data:/data" \
  -e FACE_GO2RTC_URL="http://IP_HOSTA:1984" \
  -e FACE_MQTT_ENABLE=1 -e FACE_MQTT_HOST="IP_BROKERA" \
  face-recognition:dev
```

UI: `http://localhost:8099`, health: `http://localhost:8099/api/health`.
Pełna lista zmiennych `FACE_*` — w [`CLAUDE.md`](../CLAUDE.md), sekcja „Komendy".
