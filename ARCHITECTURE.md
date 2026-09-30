# Arquitectura

Laboratorio ML tiene cuatro servicios. Nginx sirve la SPA en loopback y envía `/api/` a FastAPI por `edge`. API, worker y Valkey comparten la red interna `core`; solo API y worker montan el volumen de producto. Valkey conserva su log AOF en un volumen separado, pero no es fuente de verdad.

La API crea entidades SQLite y jobs antes de encolarlos. SQLite funciona también como outbox: ante una caída de la cola el job queda durable y se reconcilia cuando vuelve Valkey. El worker recupera trabajos pendientes tras reinicios, ejecuta cada análisis en un proceso aislado, mantiene heartbeat y termina de forma recursiva el árbol de procesos al cancelar o alcanzar el timeout. Publica primero en temporales del mismo volumen y solo al finalizar congela `analysis_result.json`; los estados mutables de jobs y artifacts quedan en SQLite. Los reportes se regeneran desde el snapshot sin volver a entrenar.

SQLite usa WAL, claves foráneas y `busy_timeout`. Las rutas se construyen con IDs internos. Los uploads originales y las versiones canónicas son inmutables. La aplicación no monta el socket Docker ni el repositorio dentro de contenedores de uso normal.

La topología reduce superficie, pero no es un firewall por dominio. La API valida Host/Origin/CSRF; el frontend usa recursos locales; el worker no recibe claves. Esta V1 es para una persona en loopback, no autenticación multiusuario ni despliegue público.
