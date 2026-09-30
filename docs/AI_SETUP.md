# Instalación asistida

1. Lee `AGENTS.md` y este archivo.
2. Verifica Docker Desktop/Engine y Compose v2, puerto 3000 y al menos 512 MiB libres.
3. Ejecuta `docker compose up --build -d` sin crear `.env` salvo que quieras cambiar defaults.
4. Espera que `docker compose ps` muestre frontend, API, worker y queue saludables.
5. Ejecuta `python scripts/smoke.py` o el smoke equivalente desde un contenedor.
6. Abre `http://localhost:3000`. No se necesita OpenAI.
7. Conserva el volumen existente. No alteres código salvo compatibilidad necesaria y registra el cambio.

Reporta `status`, `app_url`, `services_checked`, `smoke_result`, `changes_made`, `limitations` y `next_action`. No uses `healthy` si solo validaste Compose.

