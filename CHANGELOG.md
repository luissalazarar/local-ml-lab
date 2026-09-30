# Changelog

## Sin publicar

- Reemplazado el distintivo `LM` por un símbolo propio (hoja de datos con una celda apartada donde se comprueba el patrón) en el encabezado y el favicon, con variantes monocromática, inversa y reducida, PNG transparente y componente `BrandSymbol`.

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
