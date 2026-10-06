#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
APP_PORT=${APP_PORT:-3000}
APP_URL="http://127.0.0.1:$APP_PORT"
command -v docker >/dev/null || { echo 'Docker no está instalado.'; exit 1; }
if ! docker info >/dev/null 2>&1; then
  if [ "$(uname -s)" = "Darwin" ] && [ -d '/Applications/Docker.app' ]; then
    echo 'Iniciando Docker Desktop y esperando que el motor quede listo...'
    open -a Docker
    i=0
    until docker info >/dev/null 2>&1; do
      i=$((i+1))
      [ "$i" -lt 120 ] || {
        echo 'Docker Desktop no pudo iniciar dentro de diez minutos.' >&2
        exit 1
      }
      sleep 5
    done
  else
    echo 'Docker está instalado, pero el motor no está en ejecución.' >&2
    exit 1
  fi
fi
docker compose version >/dev/null
published_port=$(docker compose port frontend 8080 2>/dev/null || true)
if command -v lsof >/dev/null 2>&1 \
  && lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  case "$published_port" in
    *:"$APP_PORT") ;;
    *)
      echo "El puerto $APP_PORT está ocupado por otro proceso. Ejecuta APP_PORT=3001 sh scripts/setup.sh." >&2
      exit 1
      ;;
  esac
fi
if [ "$(uname -s)" = "Darwin" ] && command -v security >/dev/null 2>&1 \
  && { security find-certificate -c 'Avast Web/Mail Shield Root' /Library/Keychains/System.keychain >/dev/null 2>&1 \
    || security find-certificate -c 'Avast Web/Mail Shield Root' "$HOME/Library/Keychains/login.keychain-db" >/dev/null 2>&1; }; then
  echo 'Aviso: Avast HTTPS inspection detectada; la excepcion TLS solo se usara durante esta construccion local.' >&2
  UV_INSECURE_HOST=${UV_INSECURE_HOST:-'pypi.org files.pythonhosted.org'}
  NPM_CONFIG_STRICT_SSL=${NPM_CONFIG_STRICT_SSL:-false}
  export UV_INSECURE_HOST NPM_CONFIG_STRICT_SSL
fi
docker compose up --build -d
echo "Esperando $APP_URL ..."
i=0
until docker compose exec -T api python -c \
  "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health/ready', timeout=3)" \
  >/dev/null 2>&1 \
  && docker compose exec -T frontend wget -q -O /dev/null http://127.0.0.1:8080/; do
  i=$((i+1))
  [ "$i" -lt 160 ] || { echo 'La aplicación no estuvo lista dentro del tiempo esperado.' >&2; exit 1; }
  sleep 3
done
docker compose cp scripts/smoke.py api:/app/setup-smoke.py
smoke_status=0
docker compose exec -T -e APP_URL=http://localhost:8000 api python /app/setup-smoke.py || smoke_status=$?
docker compose exec -T api rm -f /app/setup-smoke.py
[ "$smoke_status" -eq 0 ] || exit "$smoke_status"
echo "Laboratorio ML está verificado y disponible en $APP_URL"
