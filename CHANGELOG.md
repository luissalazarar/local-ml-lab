# Changelog

## 1.0.3 — 2026-10-06

- Aclarado en la app qué es la referencia simple (mediana o promedio en números, clase más frecuente en categorías, último valor en series) y en base a qué se decide que un modelo es mejor: misma métrica y datos no vistos, mejora suficiente (3 % del error o 0,02), consistencia (6 de cada 10 pruebas, mediana a favor) y simplicidad ante empates. Solo cambian textos de Inicio, Guía, Evaluación en vivo y Resultados; la política de selección no cambia.

## 1.0.0 — 2026-10-02

- Ampliado a 200 MiB el tamaño máximo por archivo; API, Compose, proxy y texto visible quedan sincronizados, con streaming en Nginx y temporales de multipart sobre el volumen local.
- Ampliada la capacidad tabular a 4 millones de filas y 20 millones de celdas, con muestreo de cabecera y hash incremental para evitar copias completas innecesarias en memoria.
- Humanizados los errores de límites propagando sus códigos estables desde el worker hasta la interfaz.
- Mostradas desde el primer paso las fuentes públicas sugeridas, reutilizando las mismas referencias de la Guía.
- Añadida exploración visual calculada en backend con heatmap de correlaciones, scatterplots y boxplots sobre una muestra determinista, excluyendo identificadores y aclarando que correlación no implica causalidad.
- Añadido en Estado un borrado global seguro de uploads, versiones, corridas, reportes e historial; bloquea trabajos activos y conserva la base, la configuración y la estructura de almacenamiento.
- Explicadas las métricas con significado del valor, dirección, referencia comparable y veredicto contextual; MAE y RMSE ya aclaran su unidad y que no existe un umbral universal.
- Mostradas las fuentes públicas de datos directamente bajo el bloque principal del Home, además de conservarlas en el asistente y la Guía.
- Añadido a cada resultado tabular un resumen inmediato de variables predictivas y un laboratorio de escenarios respaldado por el modelo seleccionado, con selectores acotados, curva dinámica y límites no causales explícitos.
- Añadida a resultados de pronóstico una vista interactiva para recorrer el futuro ya calculado y contrastar cada mes con su error histórico, sin reentrenar ni inventar drivers externos.
- Cambiado el análisis nuevo a “Automático recomendado” por defecto para que modelos lineales y no lineales compitan con la misma validación; la sensibilidad ahora identifica y explica la forma observada de la curva sin imponer un ajuste separado.
- Corregidos solapamientos en gráficos de regresión, pronóstico y escenarios mediante márgenes amplios y etiquetas de ejes espaciadas de forma determinista.

## 0.7.0 — 2026-09-30

- Añadida `selection-policy-2.1`: el ganador provisional tabular del modo recomendado se vuelve a comparar con la referencia en tres separaciones reproducibles cuando existe soporte; una mejora no confirmada conserva la referencia.
- Persistidos previews LIVE atómicos y acotados fuera de los eventos, con hashes, métricas backend, comparación, trayectoria, diagnóstico por problema y replay sin nuevos ajustes.
- Incorporados diagnósticos de error por horizonte a partir de predicciones históricas existentes, P90 de error, métricas por clase y advertencias de cobertura cero.
- Cerrada la narrativa guiada de selección, confirmación, prueba reservada, resultados, historial, estado, Guía de 20 secciones y exportaciones ampliadas.

## 0.6.0 — 2026-09-30

- Añadido `AnalysisPlan` inmutable con membresía reproducible, seeds SHA-256, parámetros, presupuestos y hash del plan.
- Sustituida la predicción cruzada opaca por evaluación explícita por candidato/unidad, duplicados en bloque, holdout reservado cuando existe soporte y métricas conjuntas desde predicciones OOS.
- Incorporada `selection-policy-2.0`: mejora práctica, consistencia, banda de simplicidad, referencia elegible y exclusión de candidatos incompletos.
- Ampliado el catálogo tabular con variantes balanceadas y el temporal con siete métodos, incluidos Holt y Holt-Winters aditivos mediante statsmodels.
- Añadidos eventos estructurados, proyección `/runs/{id}/live`, polling recuperable con ETag/backoff y pantalla “Así estamos evaluando tu data”.
- Extendidos resultados, reportes, Guía y pruebas para distinguir selección, prueba reservada, futuro, estado técnico y límites.

## 0.5.0 — 2026-09-30

- Reemplazada la tabla horizontal de preparación por una experiencia master-detail, buscable y responsive que presenta una columna a la vez.
- Añadida divulgación progresiva y ayuda accesible para tipos, usos, fechas, números, recetas, métricas, exclusiones y límites.
- Incorporados controles visuales para los filtros seguros y la unificación explícita de categorías ya soportados por el backend.
- Reforzado el flujo Original → Preparado → Análisis → Entrenamiento en preparación, objetivo, revisión, resultados, Guía y reportes.
- Humanizados preview, diccionario del Excel preparado, disponibilidad del resultado, preflight, progreso, drivers y conteos de filas.

## 0.4.0 — 2026-09-30

- Añadido el paso explícito Preparar con tipo, uso y transformación separados, recomendaciones conservadoras y preview antes/después.
- Incorporadas conversiones confirmadas de fechas, números localizados, porcentajes y moneda única; trim, vacío a faltante, duplicados exactos, filtros seguros y agregación mensual explícita.
- Extendida `DatasetVersion` con receta estricta, cuarentena, perfiles original/preparado, hashes deterministas y lineage sin modificar el archivo original.
- Añadidas descargas de receta JSON y Excel preparado con cinco hojas y protección contra fórmulas.
- Integrada la preparación en objetivo, forecasting, historial, resultados, Excel/PDF y un sexto ejemplo educativo.
- Añadidas pruebas de separación contra leakage, determinismo, conversiones, segregación y flujo frontend.

## 0.3.0 — 2026-09-30

- Convertida la experiencia principal en Excel-first, con guía de estructura, selección de hoja y fila de encabezados, y mensajes educativos en perfilado, preflight, progreso y resultados.
- Añadidos cinco ejemplos guiados reproducibles en XLSX para regresión, clasificación, pronóstico, drivers y exploración, con presets revisables y validaciones de configuraciones incoherentes.
- Incorporada la sección Guía con conceptos, preparación de data, métricas, modelos, límites y enlaces públicos para practicar.
- Añadido `version.json` como fuente de verdad, mirrors SemVer, chequeo automático, versión visible en UI y release discreta en reportes nuevos.
- Renovada la identidad visual con símbolo propio, autoría, navegación, responsive y movimiento reducido, sin cambiar los contratos analíticos.

## 0.2.0 — 2026-09-30

- Recuperado y versionado el lector CSV/XLSX/Parquet con límites, selección de hoja/header y parsing conservador.
- Corregidos entrypoints Docker, persistencia de cola, health/restart y resolución dinámica API del frontend.
- Aplicadas columnas y métrica principal; preprocessing y PFI fuera de train por fold.
- Acotado forecasting a meses regulares, con horizonte configurable, agregación explícita y futuro visible.
- Añadidos cancelación de procesos descendientes, heartbeat, timeout, estados diferenciados y recuperación por outbox.
- Añadidas predicciones, errores, gráficos, matriz de confusión, soporte, reportes completos y artifacts inmutables.
- Añadidos borrado referencial seguro, smokes E2E, CI desde checkout limpio y cierre trazable de auditoría.

## 0.1.0

- Primera versión local-first: carga, perfilado, análisis predictivo ligero, historial, reportes y contexto offline.
