// Textos que explican la referencia simple y cuándo un modelo "es mejor".
// Solo describen la política de backend/src/local_ml_lab/ml/selection.py; no calculan ni cambian nada.

const ERROR_METRICS = ['mae', 'rmse']

export function referenceRule(problemType?: string | null, metricId?: string | null) {
  if (problemType === 'forecasting') return 'usa la mejor regla histórica simple disponible —último valor, media histórica o patrón estacional— sin usar variables externas'
  if (problemType === 'classification') return 'predice siempre la clase más frecuente, sin usar ninguna variable'
  if (problemType === 'regression') {
    return metricId === 'mae'
      ? 'predice siempre la mediana de los datos de entrenamiento, sin usar ninguna variable'
      : 'predice siempre el promedio de los datos de entrenamiento, sin usar ninguna variable'
  }
  return 'es una regla que no aprende, como predecir siempre la mediana, la clase más frecuente o una pauta histórica simple'
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

export const sharedEvaluationRule = 'Primero se congela el plan de particiones. En cada prueba, ambos se ajustan solo con el entrenamiento y se comparan sobre exactamente los mismos casos apartados. Así una diferencia no se debe a que uno recibió casos más fáciles.'

export const confirmationRule = 'En modo recomendado, si hay soporte suficiente y un modelo aprendido queda provisionalmente arriba, solo ese modelo y la referencia repiten 3 separaciones reproducibles nuevas. Debe mejorar en conjunto, ganar al menos 2 de esas 3 y mantener una mediana favorable; si no, se conserva la referencia. Esta comprobación no ve la prueba reservada.'

export function betterMeans(metricId?: string | null) {
  if (isErrorMetric(metricId)) return 'comete menos error'
  return metricId === 'r2' ? 'se ajusta mejor' : 'acierta más'
}
