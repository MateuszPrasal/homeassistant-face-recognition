#!/usr/bin/env sh
# Skrypt startowy add-onu. Ingress kieruje ruch na FACE_PORT wewnątrz kontenera.
set -e
exec uvicorn app.main:app --host 0.0.0.0 --port "${FACE_PORT:-8099}"
