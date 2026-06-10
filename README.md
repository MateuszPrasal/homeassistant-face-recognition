# Home Assistant — rozpoznawanie twarzy

Osobny serwis (add-on HA OS) rozpoznający twarze domowników na podstawie kamery
IP. Z Home Assistant rozmawia przez MQTT. Architektura i decyzje: [`CLAUDE.md`](CLAUDE.md).
Plan wdrożenia fazami: [`PLAN.md`](PLAN.md).

**Instalacja w Home Assistant:** [`docs/INSTALL.md`](docs/INSTALL.md).

## Struktura

```
backend/    FastAPI — REST API, worker ML (kaskada osoba→twarz), serwowanie statyku
frontend/   Next.js (output: export) — UI panelu, osadzony w HA przez Ingress
addon/      Pakowanie jako add-on HA OS (config.yaml, Dockerfile, run)
docs/       Przykłady (automatyzacje HA itp.)
```

## Wymagania dev

- **Python 3.12** (backend, venv przez `uv`) — nie 3.14 (koła ML na arm64).
- **Node 24** (frontend, Next.js).

## Szybki start (dev)

```bash
# Backend
cd backend
uv venv --python 3.12
uv sync
uv run uvicorn app.main:app --reload --port 8099

# Frontend (osobny terminal, Node 24)
cd frontend
npm install
npm run dev        # tryb dev Next
npm run build      # statyczny export do ../backend/static
```

W produkcji (add-on) backend serwuje zbudowany statyczny front — bez runtime Node.
