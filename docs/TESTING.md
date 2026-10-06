# Pruebas

El backend usa pytest para lectores reales, métricas, splits congelados, política controlada, duplicados, PFI, los siete métodos temporales, procesos cancelables, proyección en vivo y reportes. El frontend usa Vitest/Testing Library; el smoke de navegador se ejecuta contra el stack real. Los smokes Docker no usan OpenAI ni datasets privados.

La pasada didáctica también cubre la ayuda contextual con teclado y Escape, el editor de una columna a la vez, lenguaje humano en preview, disponibilidad de filas para el resultado, agregación mensual contextual y el flujo Original → Preparado → Análisis → Entrenamiento. El QA visual obligatorio incluye 1440, 768 y 390 px, zoom 200 %, teclado y ausencia de scroll horizontal de página en Preparar.

La aceptación v0.7 usa casos sintéticos fijos: constante, tendencia, estacional, tendencia estacional, ruido, cambio de nivel, ceros/negativos e historia corta con horizontes 1/3/6/12/24; además relación tabular lineal/no lineal, ruido, pocos datos, desbalance, multiclase, target constante, singleton, selección vacía, duplicados, missing target y categorías nuevas. No se cambian seeds para obtener un ganador atractivo. También se comprueban gates minimize/maximize, confirmación pass/fail/not-run, holdout sin reselección, leakage por prefijo/train, preview atómico, replay, ranking sin parciales, cancelación, recuperación y estado en vivo.

```bash
python3 scripts/check_version.py
cd backend && uv run pytest
uv run --project backend python scripts/model_selection_acceptance.py
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
