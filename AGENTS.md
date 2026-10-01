# AGENTS.md — Laboratorio ML

Este repositorio implementa una aplicación local-first y CPU-first para analizar CSV, XLSX y Parquet sin exigir conocimientos de machine learning.

## Arquitectura

- `frontend/`: React 19 + Vite; nunca recalcula métricas.
- `backend/src/local_ml_lab/`: API FastAPI, SQLite, jobs RQ y motor scikit-learn.
- `queue`: Valkey transporta únicamente identificadores de jobs.
- `/data`: volumen persistente compartido por API y worker; SQLite es la fuente de verdad.
- `analysis_result.json`: snapshot analítico inmutable. Los reportes y explicaciones no lo reescriben.
- Los previews LIVE se publican atómicamente bajo `/data/runs/{run}/live`, con un máximo determinista de 500 predicciones; eventos y replay no disparan fits nuevos.
- La preparación es `Original → DatasetVersion preparada → Modelo`; guarda receta, cuarentena y hashes, y nunca modifica el original.
- Forecasting V1 significa exclusivamente una serie mensual regular, sin huecos rellenados ni bandas inventadas.
- La validación tabular aleatoria requiere registros independientes; rechaza o declara fuera de alcance grupos y usos temporales.

## Invariantes

1. Construir y compartir splits antes de comparar modelos.
2. Ajustar imputación, categorías, escalado y selección solo en train.
3. No usar holdout para tuning ni cambiar el ganador al ver el test.
4. Un baseline puede ganar. Un candidato incompleto no puede ganar.
5. La confirmación tabular compara solo referencia y provisional dentro de desarrollo; nunca ve holdout y una mejora no confirmada conserva la referencia.
6. No convertir métricas indefinidas en cero ni serializar NaN/Infinity.
7. No llamar probabilidad a la confiabilidad ni causalidad a una importancia.
8. No enviar datos externamente por defecto. Una key OpenAI nunca se persiste ni llega al worker.
9. No importar scripts, datos, modelos o reglas privadas. Los ejemplos son sintéticos.
10. No sustituir producción por mocks; los mocks pertenecen a tests.
11. No borrar datos persistentes para resolver un fallo de arranque.
12. `version.json` owns the visible `MAJOR.MINOR.BUILD` release. Su `semver` debe coincidir con backend, frontend y lockfile; los cambios solo documentales no publican versión.
13. Preparar representaciones no es preprocesar el modelo: imputación, escalado, encoding y selección aprendida permanecen dentro de train/fold.

## Comandos

```bash
docker compose up --build -d
docker compose ps
python scripts/smoke.py
docker compose logs --tail=100 api worker
python3 scripts/cancel_smoke.py
```

Backend: `cd backend && uv sync --frozen --extra dev && uv run pytest && uv run ruff check .`.
Frontend: `cd frontend && npm ci && npm run typecheck && npm run test -- --run && npm run build`.
Versión: `python3 scripts/check_version.py`.

Antes de publicar, prueba desde un checkout limpio con nombre de proyecto, volumen y puerto Compose separados. Verifica descargas abriendo XLSX/PDF, reinicio persistente, cola caída/recuperada y ausencia de datos privados. No afirmes compatibilidad con una plataforma no probada.

Al agregar un modelo, declarar capacidades en el registry, usar el pipeline por fold, respetar clases/splits, acotar recursos y probar fallo/timeout y shapes. No cambies métricas, políticas o umbrales silenciosamente. Para cambios en contratos, sincroniza frontend, API, exportaciones y documentación.

Reporta con precisión qué se ejecutó y qué no. Usa datasets pequeños; no entrenes exhaustivo para verificar cambios ordinarios. Nunca imprimas claves, cookies, uploads ni celdas privadas en logs.
