# Privacidad

Los datasets y resultados viven en el volumen local. La instalación no incluye trackers ni envía datos por defecto. Una sesión opaca HttpOnly y un token CSRF reducen el riesgo de sitios externos contra la API local; no son autenticación multiusuario.

El contexto para IA tiene tres niveles: (1) estructura/métricas con alias, (2) añade nombres de columnas, (3) una muestra elegida explícitamente. La proyección se reconstruye mediante allowlist. Esta versión permite previsualizar y copiar ese contexto; el envío directo a OpenAI y la gestión temporal de una API key quedan pendientes.

Para borrar datos usa la interfaz cuando el recurso no esté activo. `docker compose down` conserva el volumen. El reset con volumen es destructivo y no es una operación rutinaria.
