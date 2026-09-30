const labels: Record<string, string> = {
  selection_oof: 'Predicción de validación', selection_validation: 'Validación de selección',
  selection_validation_folds: 'Particiones de validación', selection_monthly_holdout: 'Validación mensual usada para seleccionar',
  selection_cv: 'Validación cruzada usada para seleccionar', history: 'Histórico observado', forecast_future: 'Pronóstico futuro',
  selection_backtest: 'Pruebas históricas de selección', final_test: 'Prueba final reservada',
  target_unit: 'Unidades del resultado', score: 'Sin unidad', class_label: 'Categoría', balanced_accuracy: 'Exactitud balanceada',
  accuracy: 'Exactitud', macro_f1: 'F1 macro', mae: 'MAE', rmse: 'RMSE', r2: 'R²', succeeded: 'Completado',
  succeeded_with_warnings: 'Completado con avisos', failed: 'No completado', cancelled: 'Cancelado', interrupted: 'Interrumpido',
  queued: 'En cola', planned: 'Planificado', completed: 'Completado', ineligible: 'No elegible', timeout: 'Tiempo agotado', running: 'En curso', ready: 'Disponible', not_evaluable: 'No evaluable', estimate_value: 'Estimar un valor',
  classify: 'Predecir una categoría', forecast: 'Estimar próximos meses', drivers: 'Entender variables útiles', explore: 'Explorar la data',
  regression: 'Regresión', classification: 'Clasificación', forecasting: 'Pronóstico mensual', exploration: 'Exploración', shap: 'Explicaciones SHAP',
  max_upload_mib: 'Tamaño máximo por archivo (MiB)', max_rows: 'Máximo de filas', max_columns: 'Máximo de columnas',
  INSUFFICIENT_ROWS: 'No hay suficientes observaciones para evaluar modelos.',
  CLASS_SUPPORT_INSUFFICIENT: 'No hay suficientes casos por clase para evaluar modelos.',
  ALL_CANDIDATES_FAILED: 'Ningún modelo pudo completar una evaluación comparable.',
  INSUFFICIENT_HISTORY: 'No hay suficiente historial mensual para evaluar y pronosticar.',
  MISSING_MONTHLY_PERIODS: 'La serie tiene meses faltantes y el pronóstico mensual necesita continuidad.',
  CONTINUOUS_TARGET_FOR_CLASSIFICATION: 'La clasificación necesita categorías, no un número continuo.',
  REGRESSION_TARGET_NOT_NUMERIC: 'Estimar un valor necesita un resultado numérico.',
  CONSTANT_TARGET: 'El resultado no cambia y no existe variación que aprender.',
  NO_USABLE_FEATURES: 'No queda ninguna variable útil para entrenar.',
  NO_FEATURES_SELECTED: 'No se seleccionaron variables; esta referencia sí puede evaluarse.',
  ONLY_REFERENCE_RECOMMENDED_FOR_TINY_SAMPLE: 'Con dos o tres filas solo se recomienda evaluar referencias.',
  REFERENCE_PREFERRED_NO_PRACTICAL_CONSISTENT_IMPROVEMENT: 'Ningún candidato superó el umbral de mejora práctica y consistencia.',
  PRACTICAL_CONSISTENT_IMPROVEMENT_WITH_SIMPLICITY_BAND: 'La mejora fue suficiente y consistente; se prefirió el método más simple dentro de la banda equivalente.',
  PLAN_READY: 'Plan de evaluación congelado',
  CANDIDATE_STARTED: 'Evaluando un candidato con el plan congelado',
  UNIT_STARTED: 'Ajustando con entrenamiento y una parte apartada',
  UNIT_COMPLETED: 'Evaluación completada con predicciones reales',
  FORECAST_ORIGIN_STARTED: 'Simulando un origen histórico',
  FORECAST_ORIGIN_COMPLETED: 'Prueba histórica completada',
  FINAL_TEST_COMPLETED: 'Prueba reservada completada sin cambiar la selección',
  FORECAST_READY: 'Pronóstico futuro generado con la receta congelada',
  SNAPSHOT_FROZEN: 'Resultado final congelado',
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
  return metricId && concepts[metricId] ? explain(metricId) : unit === 'score' ? 'Resultado sin unidad; no es una probabilidad.' : humanLabel(unit)
}

export function systemError(message: string) {
  const code = Object.keys(labels).find(key => message.includes(key))
  return code ? labels[code] : message
}

export function progressMessage(stage?: string, message?: string) {
  if (message && labels[message]) return labels[message]
  if (message?.startsWith('Comparando modelos')) return message
  if (message?.startsWith('Midiendo importancia')) return message
  const byStage: Record<string, string> = {
    prepare: 'Preparando las variables para el análisis',
    fit: 'Comparando modelos con las mismas particiones',
    compare: 'Comparando evidencia frente a la referencia',
    evaluate: 'Calculando métricas de validación',
    explain: 'Midiendo qué variables ayudaron a predecir',
    freeze_result: 'Guardando un resultado inmutable',
    finished: 'Análisis completado',
  }
  return byStage[stage ?? ''] ?? 'Preparando el análisis…'
}

export function driverBar(importance: number, maxAbs: number) {
  return { side: importance < 0 ? 'negative' : 'positive', width: Math.abs(importance) / Math.max(maxAbs, 1e-12) * 50 }
}
import { concepts, explain } from '../education/concepts'
