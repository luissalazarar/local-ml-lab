// Textos que explican la referencia simple y cuándo un modelo "es mejor".
// Solo describen la política de backend/src/local_ml_lab/ml/selection.py; no calculan ni cambian nada.

const ERROR_METRICS = ['mae', 'rmse']

export function referenceRule(problemType?: string | null, metricId?: string | null) {
  if (problemType === 'forecasting') return 'repite el último valor conocido de la serie, sin aprender nada'
  if (problemType === 'classification') return 'predice siempre la clase más frecuente, sin usar ninguna variable'
  if (problemType === 'regression') {
    return metricId === 'mae'
      ? 'predice siempre la mediana de los datos de entrenamiento, sin usar ninguna variable'
      : 'predice siempre el promedio de los datos de entrenamiento, sin usar ninguna variable'
  }
  return 'es una regla que no aprende, como predecir siempre la mediana, la clase más frecuente o el último valor'
}

export function isErrorMetric(metricId?: string | null) {
  return ERROR_METRICS.includes(metricId ?? '')
}

export function improvementRule(metricId?: string | null) {
  if (isErrorMetric(metricId)) return 'su error tiene que ser al menos 3 % menor que el error de la referencia'
  return 'su métrica tiene que subir al menos 0,02 sobre la de la referencia'
}

export function tieRule(metricId?: string | null) {
  if (isErrorMetric(metricId)) return 'a menos de 1 % del error de la referencia'
  return metricId === 'r2' ? 'a menos de 0,01 de diferencia' : 'a menos de 0,005 de diferencia'
}

export const consistencyRule = 'tiene que ganarle a la referencia en al menos 6 de cada 10 pruebas (y haber al menos 3 pruebas), y la mediana de esas diferencias tiene que ser a su favor'

export function betterMeans(metricId?: string | null) {
  if (isErrorMetric(metricId)) return 'comete menos error'
  return metricId === 'r2' ? 'se ajusta mejor' : 'acierta más'
}
