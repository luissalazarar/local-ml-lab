#!/bin/sh
set -eu
case "${1:-api}" in
  api) exec python -m local_ml_lab.main ;;
  worker) exec worker-entrypoint.sh ;;
  *) exec "$@" ;;
esac

