# Pruebas

El backend usa pytest para lectores reales, métricas, folds, PFI, forecast, procesos cancelables y reportes. El frontend usa Vitest/Testing Library; el smoke de navegador se ejecuta contra el stack real. Los smokes Docker no usan OpenAI ni datasets privados.

```bash
python3 scripts/check_version.py
cd backend && uv run pytest
cd frontend && npm run typecheck && npm run lint && npm run test -- --run && npm run build
docker compose config
python3 scripts/smoke.py
python3 scripts/examples_smoke.py
python3 scripts/excel_smoke.py
python3 scripts/cancel_smoke.py
docker compose exec -T worker python - < scripts/verify_reports.py
```

`smoke.py` recorre regresión, clasificación desbalanceada y forecasting mensual usando los Excel principales; verifica métrica principal, PFI fuera de train, matriz de confusión, futuro visible, historial, contexto offline y descargas reales. `examples_smoke.py` ejecuta los cinco presets publicados y exige que ninguno termine como no evaluable. `cancel_smoke.py` cancela durante el último candidato y exige estado `cancelled` sin resultado. `recovery_smoke.py` se usa al detener Valkey: exige HTTP 503 y posterior recuperación.

Para la puerta de salida usa un checkout limpio y aislado:

```bash
APP_PORT=33000 docker compose -p local-ml-lab-check up --build -d
APP_URL=http://localhost:33000 python3 scripts/smoke.py
APP_URL=http://localhost:33000 python3 scripts/cancel_smoke.py
APP_PORT=33000 docker compose -p local-ml-lab-check restart
```

No reutilices `.venv`, `node_modules`, volúmenes ni datos del checkout de desarrollo. Los tests usan datasets pequeños y árboles acotados; mocks solo en pruebas unitarias.
