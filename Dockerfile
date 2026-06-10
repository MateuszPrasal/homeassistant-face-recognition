# Obraz bazowy runtime — globalny ARG, by był widoczny w FROM (nadpisywany przez
# Supervisora z build.yaml; lokalnie domyślnie python:3.12-slim).
ARG BUILD_FROM=python:3.12-slim

# ---- Stage 1: build frontu (Next.js static export) ----
FROM node:24-slim AS frontend
WORKDIR /frontend
# Najpierw manifesty — cache warstwy npm, gdy kod się zmienia a deps nie.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# `next build` (output:'export') → /frontend/out, potem relativize.mjs robi
# ścieżki assetów względne (Ingress) — patrz scripts/relativize.mjs.
RUN npm run build:export

# ---- Stage 2: runtime (backend FastAPI + statyczny front) ----
ARG BUILD_FROM=python:3.12-slim
FROM ${BUILD_FROM} AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FACE_STATIC_DIR=/app/static \
    FACE_DATA_DIR=/data \
    FACE_MODELS_DIR=/data/models \
    FACE_PORT=8099

WORKDIR /app

# opencv-python-headless wymaga libglib2.0-0; onnxruntime wymaga libgomp1 (OpenMP).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Zależności backendu. TODO (Faza 5): zastąpić jawną listę lockfile (uv export).
# Modele ONNX dociągają się przy pierwszym starcie do FACE_MODELS_DIR (/data/models).
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir \
        fastapi "uvicorn[standard]" httpx numpy opencv-python-headless \
        onnxruntime python-multipart paho-mqtt

# Kod backendu + zbudowany front + skrypt startowy.
COPY backend/app ./app
COPY --from=frontend /frontend/out ./static
COPY run.sh /run.sh
RUN chmod +x /run.sh

EXPOSE 8099
CMD ["/run.sh"]
