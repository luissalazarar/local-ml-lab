#!/bin/sh
set -eu
command -v docker >/dev/null || { echo 'Docker no está instalado.'; exit 1; }
docker version >/dev/null
docker compose version >/dev/null
docker compose up --build -d
echo 'Esperando http://localhost:3000 ...'
i=0; until wget -q -O /dev/null http://localhost:3000/api/v1/health/ready; do i=$((i+1)); [ "$i" -lt 160 ] || exit 1; sleep 3; done
echo 'Laboratorio ML está disponible en http://localhost:3000'

