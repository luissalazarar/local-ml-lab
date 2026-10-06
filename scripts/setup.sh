#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
INSTALL_DOCKER=0
case "${1:-}" in
  '') ;;
  --install-docker) INSTALL_DOCKER=1 ;;
  *) echo "Uso: sh scripts/setup.sh [--install-docker]" >&2; exit 2 ;;
esac

install_docker_desktop() {
  [ "$(uname -s)" = "Darwin" ] || {
    echo 'La instalación automática de Docker solo está disponible aquí para macOS.' >&2
    exit 1
  }
  case "$(uname -m)" in
    arm64) docker_arch=arm64 ;;
    x86_64) docker_arch=amd64 ;;
    *) echo "Arquitectura de macOS no soportada: $(uname -m)" >&2; exit 1 ;;
  esac
  command -v curl >/dev/null || { echo 'macOS no tiene curl disponible.' >&2; exit 1; }
  docker_tmp=$(mktemp -d "${TMPDIR:-/tmp}/local-ml-lab-docker.XXXXXX")
  docker_mount="$docker_tmp/mount"
  mkdir -p "$docker_mount"
  cleanup_docker_installer() {
    hdiutil detach "$docker_mount" >/dev/null 2>&1 || true
    rm -f "$docker_tmp/Docker.dmg"
    rmdir "$docker_mount" "$docker_tmp" >/dev/null 2>&1 || true
  }
  trap cleanup_docker_installer 0 1 2 15
  echo 'Descargando Docker Desktop desde Docker…'
  curl --fail --location --retry 3 --output "$docker_tmp/Docker.dmg" \
    "https://desktop.docker.com/mac/main/$docker_arch/Docker.dmg"
  hdiutil attach -nobrowse -mountpoint "$docker_mount" "$docker_tmp/Docker.dmg" >/dev/null
  echo 'Instalando Docker Desktop. macOS puede mostrar una ventana protegida para autorizarlo.'
  osascript - "$docker_mount/Docker.app/Contents/MacOS/install" "$USER" <<'APPLESCRIPT'
on run arguments
  set installerPath to item 1 of arguments
  set userName to item 2 of arguments
  do shell script quoted form of installerPath & " --accept-license --user=" & quoted form of userName with administrator privileges
end run
APPLESCRIPT
  cleanup_docker_installer
  trap - 0 1 2 15
}

if ! command -v docker >/dev/null 2>&1; then
  for docker_bin in "$HOME/.docker/bin" '/Applications/Docker.app/Contents/Resources/bin'; do
    [ -x "$docker_bin/docker" ] && PATH="$docker_bin:$PATH"
  done
  export PATH
fi
if ! command -v docker >/dev/null 2>&1; then
  [ "$INSTALL_DOCKER" -eq 1 ] || {
    echo 'Docker no está instalado. Ejecuta: sh scripts/setup.sh --install-docker' >&2
    exit 1
  }
  install_docker_desktop
  PATH="$HOME/.docker/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"
  export PATH
fi
APP_PORT=${APP_PORT:-3000}
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
      requested_port=$APP_PORT
      APP_PORT=3001
      while lsof -nP -iTCP:"$APP_PORT" -sTCP:LISTEN >/dev/null 2>&1; do
        APP_PORT=$((APP_PORT+1))
        [ "$APP_PORT" -le 3099 ] || { echo 'No hay un puerto libre entre 3001 y 3099.' >&2; exit 1; }
      done
      export APP_PORT
      echo "El puerto $requested_port estaba ocupado; se usará $APP_PORT."
      ;;
  esac
fi
APP_URL="http://127.0.0.1:$APP_PORT"
if [ "$(uname -s)" = "Darwin" ] && command -v security >/dev/null 2>&1 \
  && { security find-certificate -c 'Avast Web/Mail Shield Root' /Library/Keychains/System.keychain >/dev/null 2>&1 \
    || security find-certificate -c 'Avast Web/Mail Shield Root' "$HOME/Library/Keychains/login.keychain-db" >/dev/null 2>&1; }; then
  echo 'Aviso: Avast HTTPS inspection detectada; la excepcion TLS solo se usara durante esta construccion local.' >&2
  UV_INSECURE_HOST=${UV_INSECURE_HOST:-'pypi.org files.pythonhosted.org'}
  NPM_CONFIG_STRICT_SSL=${NPM_CONFIG_STRICT_SSL:-false}
  export UV_INSECURE_HOST NPM_CONFIG_STRICT_SSL
fi
build_attempt=1
while ! docker compose up --build -d; do
  [ "$build_attempt" -lt 3 ] || {
    echo 'La construcción falló tres veces. Revisa la conexión o proxy y vuelve a ejecutar el mismo comando; los datos se conservan.' >&2
    exit 1
  }
  build_attempt=$((build_attempt+1))
  echo "La descarga o construcción falló; reintentando ($build_attempt de 3)…" >&2
  sleep 5
done
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
if [ "$(uname -s)" = "Darwin" ]; then
  open "$APP_URL" >/dev/null 2>&1 || echo "Abre $APP_URL en tu navegador."
fi
