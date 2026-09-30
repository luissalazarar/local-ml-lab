const labels: Record<string, string> = {
  selection_oof: 'Predicción de validación', selection_validation: 'Validación de selección',
  selection_validation_folds: 'Particiones de validación', selection_monthly_holdout: 'Validación mensual usada para seleccionar',
  selection_cv: 'Validación cruzada usada para seleccionar', history: 'Histórico observado', forecast_future: 'Pronóstico futuro',
  target_unit: 'Unidades del resultado', score: 'Sin unidad', class_label: 'Categoría', balanced_accuracy: 'Exactitud balanceada',
  accuracy: 'Exactitud', macro_f1: 'F1 macro', mae: 'MAE', rmse: 'RMSE', r2: 'R²', succeeded: 'Completado',
  succeeded_with_warnings: 'Completado con avisos', failed: 'No completado', cancelled: 'Cancelado', interrupted: 'Interrumpido',
  queued: 'En cola', running: 'En curso', ready: 'Disponible', not_evaluable: 'No evaluable', estimate_value: 'Estimar un valor',
  classify: 'Predecir una categoría', forecast: 'Estimar próximos meses', drivers: 'Entender variables útiles', explore: 'Explorar la data',
  regression: 'Regresión', classification: 'Clasificación', forecasting: 'Pronóstico mensual', exploration: 'Exploración', shap: 'Explicaciones SHAP',
  max_upload_mib: 'Tamaño máximo por archivo (MiB)', max_rows: 'Máximo de filas', max_columns: 'Máximo de columnas',
  INSUFFICIENT_ROWS: 'No hay suficientes observaciones para evaluar modelos.',
  CLASS_SUPPORT_INSUFFICIENT: 'No hay suficientes casos por clase para evaluar modelos.',
  ALL_CANDIDATES_FAILED: 'Ningún modelo pudo completar una evaluación comparable.',
  INSUFFICIENT_HISTORY: 'No hay suficiente historial mensual para evaluar y pronosticar.',
}

export function humanLabel(value: string | null | undefined, fallback?: string) {
  if (!value) return fallback ?? 'No disponible'
  return labels[value] ?? fallback ?? value.replaceAll('_', ' ')
}

export function metricLabel(metricId: string | null | undefined, name?: string) {
  if (!metricId) return name ?? 'Sin métrica predictiva'
  return labels[metricId] ?? (name === 'R2' ? 'R²' : name ?? metricId.toUpperCase())
}

export function metricExplanation(metricId: string | null | undefined, unit?: string) {
  switch (metricId) {
    case 'mae': return 'Error absoluto medio, en la unidad del resultado.'
    case 'rmse': return 'Raíz del error cuadrático medio; penaliza más los errores grandes.'
    case 'r2': return 'R² no es un porcentaje de acierto y puede ser negativo.'
    case 'balanced_accuracy': return 'Promedio del acierto obtenido en cada clase.'
    case 'accuracy': return 'Proporción de categorías predichas correctamente.'
    case 'macro_f1': return 'Promedio del equilibrio entre precisión y cobertura de cada clase.'
    default: return unit === 'score' ? 'Resultado sin unidad; no es una probabilidad.' : humanLabel(unit)
  }
}

export function systemError(message: string) {
  const code = Object.keys(labels).find(key => message.includes(key))
  return code ? labels[code] : message
}

export function driverBar(importance: number, maxAbs: number) {
  return { side: importance < 0 ? 'negative' : 'positive', width: Math.abs(importance) / Math.max(maxAbs, 1e-12) * 50 }
}
