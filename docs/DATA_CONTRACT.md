# Contrato de datos y API

Los contratos usan `schema_version: "1.0"`, UUID externos, timestamps UTC y números JSON finitos. Columnas se identifican como `c0001`; los nombres originales nunca son rutas ni claves ejecutables.

Flujo principal: `POST /datasets` → versión → `POST /preflights` → `POST /runs` → resultado. Las mutaciones requieren sesión local y CSRF. Los trabajos devuelven 202 y se consultan por `/jobs/{id}`. El resultado analítico es inmutable y lleva ETag. Los reportes se solicitan aparte.

Errores esperados usan `{error:{code,message,field_errors,retryable,request_id}}`. Las rutas de descarga aceptan `artifact_id`, comprueban contención bajo `/data` y fuerzan descarga.

