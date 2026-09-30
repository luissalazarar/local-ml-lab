# Changelog

## Sin publicar

- Sin cambios todavía.

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
