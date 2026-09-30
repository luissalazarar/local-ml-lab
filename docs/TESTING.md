# Pruebas

El backend usa pytest para parsing, métricas, invariantes y API. El frontend usa Vitest/Testing Library y Playwright para smoke. El smoke Docker real crea un ejemplo, prepara versión, preflight, análisis y reportes; no usa OpenAI.

```bash
cd backend && uv run pytest
cd frontend && npm run typecheck && npm run test -- --run && npm run build
docker compose config
python scripts/smoke.py
```

Los tests deben usar datasets pequeños y árboles reducidos. Mocks solo en pruebas; el smoke de integración usa la API y el worker reales.

