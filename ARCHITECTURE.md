# Arquitectura

Laboratorio ML tiene cuatro servicios. Nginx sirve la SPA en loopback y envía `/api/` a FastAPI por `edge`. API, worker y Valkey comparten la red interna `core`; solo API y worker montan el volumen. Valkey no es fuente de verdad.

La API crea entidades SQLite y jobs antes de encolarlos. El worker reclama una operación, actualiza eventos persistentes y publica primero en temporales del mismo volumen. Al finalizar congela `analysis_result.json`; los estados mutables de jobs y artifacts quedan en SQLite. Los reportes se regeneran desde el snapshot sin volver a entrenar.

SQLite usa WAL, claves foráneas y `busy_timeout`. Las rutas se construyen con IDs internos. Los uploads originales y las versiones canónicas son inmutables. La aplicación no monta el socket Docker ni el repositorio dentro de contenedores de uso normal.

La topología reduce superficie, pero no es un firewall por dominio. La API valida Host/Origin/CSRF; el frontend usa recursos locales; el worker no recibe claves. Esta V1 es para una persona en loopback, no autenticación multiusuario ni despliegue público.

