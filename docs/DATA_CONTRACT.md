# Contrato de datos y API

Los contratos usan `schema_version: "1.0"`, UUID externos, timestamps UTC y números JSON finitos. Columnas se identifican como `c0001`; los nombres originales nunca son rutas ni claves ejecutables.

Flujo principal: `POST /datasets` → versión → `POST /preflights` → `POST /runs` → resultado. Las mutaciones requieren sesión local y CSRF. Los trabajos aceptados devuelven 202 y se consultan por `/jobs/{id}`. Si la cola no está disponible, la API conserva el job en SQLite y devuelve 503 con su identificador; el outbox del worker lo recupera cuando vuelve Valkey. El resultado analítico es inmutable y lleva ETag. Los reportes se solicitan aparte, son artefactos con identidad propia y una falla al exportar no cambia el resultado analítico.

`RunResult schema_version=2.0` añade `analysis_plan`, `plan_sha256`, catálogo ejecutado, elegibilidad/fallos, métricas conjuntas y por unidad, `selection-policy-2.0`, best observed/selected/baseline, prueba reservada separada, forecast, alcance de explicación, duración e integridad. Los snapshots históricos 1.x siguen siendo legibles y nunca se reescriben.

`GET /runs/{run_id}/live` devuelve la proyección mutable del intento activo: timestamps reales, revisión, resumen del plan, contadores, candidatos, ranking solo de completos, preview acotado, eventos recientes y disponibilidad final. Soporta ETag. `GET /jobs/{job_id}/events?after=<seq>&limit=<1..200>` pagina eventos; no expone un historial infinito.

Los eventos incluyen versión, run/job/attempt, seq, timestamp, tipo, etapa, candidato, unidad, rol de evaluación y message code. Las previews contienen como máximo 200 predicciones; la UI no recalcula métricas. Datos, targets, muestras y errores nunca se envían a servicios externos.

Errores esperados usan `{error:{code,message,field_errors,retryable,request_id}}`. Las rutas de descarga aceptan `artifact_id`, comprueban contención bajo `/data` y fuerzan descarga. `POST /runs` deduplica por preflight activo/completado y las exportaciones activas por conjunto de formatos, de modo que un doble clic no crea trabajo duplicado.
