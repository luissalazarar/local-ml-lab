#!/bin/sh
set -eu
docker version >/dev/null && echo '[OK] Docker Engine'
docker compose version >/dev/null && echo '[OK] Docker Compose'
docker compose config --quiet && echo '[OK] Compose'
wget -q -O - http://localhost:3000/api/v1/system
docker compose ps

