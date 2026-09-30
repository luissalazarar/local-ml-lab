# Instalación asistida

1. Lee `AGENTS.md` y este archivo.
2. Verifica Docker Desktop/Engine y Compose v2, puerto 3000 y al menos 4 GiB disponibles para construir.
3. Ejecuta `docker compose up --build -d` sin crear `.env` salvo que quieras cambiar defaults.
4. Espera que `docker compose ps` muestre frontend, API, worker y queue saludables.
5. Ejecuta `python3 scripts/smoke.py`; debe recorrer regresión, clasificación, forecast y abrir descargas XLSX/PDF.
6. Para una validación de release, ejecuta también `python3 scripts/cancel_smoke.py`, reinicia Compose y confirma que el historial persiste. `scripts/recovery_smoke.py` documenta la prueba de cola caída.
7. Abre `http://localhost:3000`. No se necesita OpenAI.
8. Conserva el volumen existente. No alteres código salvo compatibilidad necesaria y registra el cambio.

Reporta `status`, `app_url`, `services_checked`, `smoke_result`, `changes_made`, `limitations` y `next_action`. No uses `healthy` si solo validaste Compose.

Si una encolación falla, la API responde `503` con el `job_id`; no la presentes como correctamente encolada. El outbox SQLite la recupera cuando vuelve la cola. No borres volúmenes para resolverlo.
