import { concepts } from './concepts'
import { metricLabel } from '../presentation/labels'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 4 })
const percent = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1, style: 'percent' })

export function metricValueMeaning(metricId: string | null | undefined, value: number | null | undefined) {
  if (!metricId || value == null) return 'Todavía no existe un valor evaluado para interpretar.'
  const shown = fmt.format(value)
  switch (metricId) {
    case 'mae': return `Un MAE de ${shown} significa que la distancia absoluta promedio entre el valor real y el predicho fue ${shown} unidades del resultado.`
    case 'rmse': return `Un RMSE de ${shown} resume el error en la unidad del resultado, dando más peso a los errores grandes. No es un porcentaje.`
    case 'r2':
      if (value < 0) return `Un R² de ${shown} indica que, en esta evaluación, rindió peor que predecir siempre el promedio.`
      if (value === 0) return 'Un R² de 0 indica un rendimiento equivalente a predecir siempre el promedio en esta evaluación.'
      return `Un R² de ${shown} supera la referencia del promedio en esta evaluación; cuanto más cerca de 1, mejor fue el ajuste.`
    case 'accuracy': return `Una exactitud de ${shown} equivale aproximadamente a ${percent.format(value)} de predicciones correctas en los casos evaluados.`
    case 'balanced_accuracy': return `Una exactitud balanceada de ${shown} promedia el acierto de cada clase dándoles el mismo peso.`
    case 'macro_f1': return `Un F1 macro de ${shown} resume precisión y cobertura por clase, dando el mismo peso a cada categoría.`
    case 'median_absolute_error': return `Una mediana de error absoluto de ${shown} significa que la mitad de los errores absolutos fue igual o menor que ${shown}.`
    case 'p90_absolute_error': return `Un P90 de error absoluto de ${shown} significa que el 90% de los errores absolutos fue igual o menor que ${shown}.`
    default: return `${metricLabel(metricId)} obtuvo ${shown} en las observaciones evaluadas.`
  }
}

export function metricComparisonGuide(metricId: string | null | undefined) {
  const item = metricId ? concepts[metricId] : undefined
  return item?.compareAgainst ?? 'Compáralo con una referencia evaluada sobre los mismos casos y con el costo real de equivocarte.'
}

type MetricInterpretationProps = {
  metricId: string | null | undefined
  value: number | null | undefined
  baselineValue?: number | null
  baselineName?: string
  selectedName?: string
  outcome?: string | null
  provisional?: boolean
}

export function MetricInterpretation({ metricId, value, baselineValue, baselineName = 'Referencia sencilla', selectedName = 'Modelo', outcome, provisional = false }: MetricInterpretationProps) {
  const item = metricId ? concepts[metricId] : undefined
  const comparable = value != null && baselineValue != null
  const direction = item?.direction === 'higher' ? 'más alto' : item?.direction === 'lower' ? 'más bajo' : 'más favorable'
  const verdict = provisional
    ? 'Esta lectura es provisional. El resultado final exige completar las pruebas y comprobar que la mejora sea suficientemente grande y consistente.'
    : outcome === 'practical_consistent_improvement'
      ? 'Para este análisis, la política confirmó una mejora práctica y consistente frente a la referencia. Eso no garantiza el mismo rendimiento con datos futuros.'
      : comparable
        ? 'Para este análisis, no quedó justificada una mejora práctica y consistente; conservar la referencia es el resultado correcto, no un fallo.'
        : 'Sin una referencia comparable no se puede afirmar que el valor sea bueno o malo. Debe contrastarse con el costo de error de tu caso real.'

  return <section className={`panel metricInterpreter${provisional ? ' provisional' : ''}`} aria-labelledby={provisional ? 'live-metric-interpretation' : 'metric-interpretation'}>
    <div className="panelTitle">
      <div>
        <span className="sectionQuestion">Cómo leer {metricLabel(metricId)}</span>
        <h2 id={provisional ? 'live-metric-interpretation' : 'metric-interpretation'}>Valor, comparación y decisión</h2>
      </div>
    </div>
    <div className="metricInterpretationGrid">
      <article><strong>1. ¿Qué significa?</strong><p>{metricValueMeaning(metricId, value)}</p></article>
      <article><strong>2. ¿Contra qué se compara?</strong><p>{comparable ? `${selectedName}: ${fmt.format(value!)}. ${baselineName}: ${fmt.format(baselineValue!)}. En ${metricLabel(metricId)}, ${direction} es mejor.` : metricComparisonGuide(metricId)}</p></article>
      <article><strong>3. ¿Está bien o mal?</strong><p>{verdict}</p>{item?.goodBad && <small>{item.goodBad}</small>}</article>
    </div>
  </section>
}
