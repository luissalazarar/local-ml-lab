#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
APP_PORT=${APP_PORT:-3000}
APP_URL="http://127.0.0.1:$APP_PORT"
docker version >/dev/null && echo '[OK] Docker Engine'
docker compose version >/dev/null && echo '[OK] Docker Compose'
docker compose config --quiet && echo '[OK] Compose'
curl -fsS "$APP_URL/api/v1/health/ready" >/dev/null && echo '[OK] API'
curl -fsS "$APP_URL/api/v1/system"
printf '\n'
docker compose ps
