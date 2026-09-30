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
python3 scripts/preparation_smoke.py
python3 scripts/cancel_smoke.py
docker compose exec -T worker python - < scripts/verify_reports.py
```

`smoke.py` recorre regresión, clasificación desbalanceada y forecasting mensual usando los Excel principales. `preparation_smoke.py` carga el Excel educativo, confirma DMY y coma decimal, marca el ID, segrega conversiones fallidas, crea la versión preparada, abre el XLSX de cinco hojas y prueba que receta/output/lineage sean reproducibles sin alterar el hash original. `examples_smoke.py` ejecuta los seis presets publicados. `cancel_smoke.py` y `recovery_smoke.py` cubren cancelación y recuperación de cola.

Para la puerta de salida usa un checkout limpio y aislado:

```bash
APP_PORT=33000 docker compose -p local-ml-lab-check up --build -d
APP_URL=http://localhost:33000 python3 scripts/smoke.py
APP_URL=http://localhost:33000 python3 scripts/cancel_smoke.py
APP_PORT=33000 docker compose -p local-ml-lab-check restart
```

No reutilices `.venv`, `node_modules`, volúmenes ni datos del checkout de desarrollo. Los tests usan datasets pequeños y árboles acotados; mocks solo en pruebas unitarias.
