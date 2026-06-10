#!/usr/bin/env sh
# Start add-onu. Obraz bazowy to python:slim (bez bashio/s6) — opcje add-onu
# z /data/options.json parsujemy samym Pythonem i eksportujemy jako FACE_*.
set -e

OPTIONS=/data/options.json
if [ -f "$OPTIONS" ]; then
    # Każda ustawiona (niepusta) opcja → odpowiedni env FACE_*. shlex.quote
    # zabezpiecza wartości ze spacjami/znakami specjalnymi.
    eval "$(python3 - "$OPTIONS" <<'PY'
import json, shlex, sys

try:
    opts = json.load(open(sys.argv[1]))
except Exception:
    opts = {}

mapping = {
    "log_level": "FACE_LOG_LEVEL",
    "go2rtc_url": "FACE_GO2RTC_URL",
    "snapshot_timeout": "FACE_SNAPSHOT_TIMEOUT",
    "match_threshold": "FACE_MATCH_THRESHOLD",
    "person_conf": "FACE_PERSON_CONF",
    "det_thresh": "FACE_DET_THRESH",
}
for key, env in mapping.items():
    val = opts.get(key)
    if val not in (None, ""):
        print(f"export {env}={shlex.quote(str(val))}")
PY
)"
fi

# uvicorn chce małych liter w --log-level; nasz logger czyta FACE_LOG_LEVEL osobno.
LOG_LEVEL=$(echo "${FACE_LOG_LEVEL:-info}" | tr 'A-Z' 'a-z')

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${FACE_PORT:-8099}" \
    --log-level "$LOG_LEVEL"
