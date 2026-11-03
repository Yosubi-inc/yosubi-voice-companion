#!/bin/sh
# Single image, two roles. Railway sets SERVICE_ROLE per service (web|scheduler)
# and injects PORT. Local `python -m app` still binds loopback for dev.
set -e
if [ "$SERVICE_ROLE" = "scheduler" ]; then
  python -m app.database
  exec python -m app.scheduler
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
