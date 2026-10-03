import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ScenarioMetadata, ScenarioResponse } from '../../api/client'
import { humanLabel } from '../../presentation/labels'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 4 })
const pct = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1, style: 'percent' })

export function ScenarioExplorer({ runId, metadata }: { runId: string, metadata?: ScenarioMetadata }) {
  const controls = useMemo(() => metadata?.controls ?? [], [metadata?.controls])
  const [values, setValues] = useState<Record<string, number | string>>(() => defaults(controls))
  const [driverId, setDriverId] = useState(() => controls[0]?.column_id ?? '')
  const [classLabel, setClassLabel] = useState(() => metadata?.class_labels?.[0] ?? '')
  const [response, setResponse] = useState<ScenarioResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!metadata?.available || !driverId || !controls.length) return
    let active = true
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      setLoading(true)
      setError('')
      void api<ScenarioResponse>(`/runs/${runId}/scenario`, {
        method: 'POST',
        signal: controller.signal,
        body: JSON.stringify({ values, driver_id: driverId, class_label: classLabel || null }),
      }).then(value => {
        if (active) setResponse(value)
      }).catch((reason: Error) => {
        if (active && reason.name !== 'AbortError') setError(reason.message)
      }).finally(() => {
        if (active) setLoading(false)
      })
    }, 220)
    return () => { active = false; window.clearTimeout(timer); controller.abort() }
  }, [classLabel, controls.length, driverId, metadata?.available, runId, values])

  if (!metadata?.available) return <section className="panel scenarioUnavailable"><span className="sectionQuestion">Probar escenarios</span><h2>Esta corrida no tiene un modelo de escenarios</h2><p>{metadata?.reason_code ? humanLabel(metadata.reason_code) : 'Fue creada antes de incorporar esta función.'} Ejecuta un análisis nuevo para guardar un modelo local preparado para esta vista.</p><Link className="button primary" to="/new">Crear una nueva corrida</Link></section>
  const modelFamily = metadata.model_family ?? response?.model_family

  return <section className="scenarioWorkspace">
    <div className="panel scenarioIntro">
      <span className="sectionQuestion">Laboratorio interactivo</span>
      <h2>¿Qué proyecta el modelo si cambias las entradas?</h2>
      <p>Modifica hasta {controls.length} variables importantes. La app conserva las demás en un valor representativo y calcula el resultado con <strong>{metadata.model_name}</strong>. La curva sigue las predicciones de ese modelo; no se le impone una recta aparte.</p>
      <div className="scenarioFacts"><span><strong>{metadata.fit_row_count?.toLocaleString('es-PE')}</strong> filas usadas al reajustar</span><span><strong>{metadata.target_name}</strong> resultado proyectado</span>{modelFamily && <span><strong>{modelFamilyLabel(modelFamily)}</strong> familia ganadora</span>}</div>
      <div className="alert warning"><strong>Escenario, no evidencia nueva</strong><span>No reevalúa el modelo, no cambia la corrida y no demuestra causalidad. Los controles se limitan al rango observado.</span></div>
    </div>
    <div className="scenarioLayout">
      <form className="panel scenarioControls" onSubmit={event => event.preventDefault()}>
        <h2>Variables de entrada</h2>
        <p>Mueve un selector y la proyección se actualiza. Esto no modifica los hiperparámetros ni reentrena el modelo.</p>
        {controls.map(control => <label className="scenarioControl" key={control.column_id}>
          <span>{control.display_name}<output>{formatControl(values[control.column_id])}</output></span>
          {control.kind === 'numeric'
            ? <input type="range" min={control.minimum} max={control.maximum} step={control.step} value={Number(values[control.column_id])} onChange={event => setValues(current => ({ ...current, [control.column_id]: Number(event.target.value) }))} />
            : <select value={String(values[control.column_id])} onChange={event => setValues(current => ({ ...current, [control.column_id]: event.target.value }))}>{control.options?.map(option => <option key={option}>{option}</option>)}</select>}
          {control.importance_mean != null && <small>Importancia predictiva: {fmt.format(control.importance_mean)}{control.options_truncated ? ' · se muestran las categorías más frecuentes' : ''}</small>}
        </label>)}
      </form>
      <div className="panel scenarioOutput" aria-live="polite">
        <div className="panelTitle"><div><span className="sectionQuestion">Resultado del escenario</span><h2>Proyección actual</h2></div>{loading && <span className="tag running">Actualizando…</span>}</div>
        {metadata.problem_type === 'classification' && <label>Clase que quieres seguir<select value={classLabel} onChange={event => setClassLabel(event.target.value)}>{metadata.class_labels?.map(label => <option key={label}>{label}</option>)}</select></label>}
        {error && <div className="alert error" role="alert">{error}</div>}
        {response && <>
          <div className="scenarioPrediction"><span>{metadata.problem_type === 'classification' ? 'Clase proyectada' : metadata.target_name}</span><strong>{formatPrediction(response.prediction)}</strong>{response.probability != null && <small>Probabilidad estimada de {response.class_label}: {pct.format(response.probability)}</small>}</div>
          <label>Variable del gráfico<select value={driverId} onChange={event => setDriverId(event.target.value)}>{controls.map(control => <option value={control.column_id} key={control.column_id}>{control.display_name}</option>)}</select></label>
          <div className="scenarioSensitivity"><strong>{shapeLabel(response.curve_shape)} · {directionLabel(response.sensitivity_direction)}</strong><span>{shapeExplanation(response.curve_shape, response.training_depth ?? metadata.training_depth)}</span></div>
          <ScenarioCurve response={response} classification={metadata.problem_type === 'classification'} />
        </>}
      </div>
    </div>
  </section>
}

function ScenarioCurve({ response, classification }: { response: ScenarioResponse, classification: boolean }) {
  if (!response.curve.length) return null
  const outputs = response.curve.map(point => point.output)
  let low = classification ? 0 : Math.min(...outputs), high = classification ? 1 : Math.max(...outputs)
  if (low === high) { low -= .5; high += .5 }
  const span = high - low
  const x = (index: number) => 58 + index / Math.max(1, response.curve.length - 1) * 522
  const y = (value: number) => 248 - (value - low) / span * 194
  const points = response.curve.map((point, index) => `${x(index)},${y(point.output)}`).join(' ')
  const labelIndices = new Set(spacedIndices(response.curve.length, 5))
  return <figure className="scenarioChart"><figcaption>Proyección de {classification ? `probabilidad de ${response.class_label}` : 'resultado'} al variar {response.driver_name}</figcaption><svg viewBox="0 0 620 300" role="img" aria-label={`Curva de proyección según ${response.driver_name}`}><line x1="58" y1="248" x2="580" y2="248" className="chartGrid"/><line x1="58" y1="54" x2="58" y2="248" className="chartGrid"/><polyline points={points} className="scenarioLine"/>{response.curve.map((point,index) => <g key={`${point.input}-${index}`}><circle cx={x(index)} cy={y(point.output)} r="4" className="scenarioPoint"><title>{`${point.input}: ${fmt.format(point.output)}`}</title></circle>{labelIndices.has(index) && <text x={x(index)} y="270" className="axisTick axisTickX">{typeof point.input === 'number' ? fmt.format(point.input) : String(point.input).slice(0, 12)}</text>}</g>)}<text x="50" y="58" className="axisTick">{classification ? '100%' : fmt.format(high)}</text><text x="50" y="248" className="axisTick">{classification ? '0%' : fmt.format(low)}</text></svg></figure>
}

function spacedIndices(length: number, count: number) {
  const size = Math.min(count, length)
  return [...new Set(Array.from({ length: size }, (_, index) => Math.round(index * (length - 1) / Math.max(size - 1, 1))))]
}

function defaults(controls: ScenarioMetadata['controls']) {
  return Object.fromEntries((controls ?? []).map(control => [control.column_id, control.default]))
}

function formatControl(value: number | string | undefined) {
  return typeof value === 'number' ? fmt.format(value) : String(value ?? '')
}

function formatPrediction(value: number | string) {
  return typeof value === 'number' ? fmt.format(value) : value
}

function modelFamilyLabel(family: string) {
  return ({ linear: 'Lineal', linear_balanced: 'Lineal balanceada', extra_trees: 'Extra Trees', random_forest: 'Random Forest', random_forest_balanced: 'Random Forest balanceado', reference: 'Referencia' } as Record<string,string>)[family] ?? family
}

function shapeLabel(shape?: ScenarioResponse['curve_shape']) {
  return ({ approximately_linear: 'Forma aproximadamente lineal', nonlinear: 'Forma no lineal', flat: 'Sin cambio apreciable', categorical: 'Comparación entre categorías' } as Record<string,string>)[shape ?? ''] ?? 'Forma no disponible'
}

function directionLabel(direction?: ScenarioResponse['sensitivity_direction']) {
  return ({ increasing: 'tendencia ascendente', decreasing: 'tendencia descendente', mixed: 'cambios de dirección', flat: 'respuesta plana', categorical: 'respuesta por categoría' } as Record<string,string>)[direction ?? ''] ?? 'dirección no disponible'
}

function shapeExplanation(shape: ScenarioResponse['curve_shape'], depth?: ScenarioMetadata['training_depth']) {
  if (depth === 'quick') return 'Esta corrida usó el catálogo rápido, que solo comparó referencia y modelo lineal. Para permitir relaciones no lineales, repite el análisis con “Automático recomendado”.'
  if (shape === 'nonlinear') return 'La curvatura proviene de las predicciones del modelo que ganó la validación compartida; no de una línea ajustada solo para este gráfico.'
  if (shape === 'approximately_linear') return 'Los modelos lineales y no lineales compitieron; la forma mostrada corresponde al ganador y a los demás valores mantenidos fijos.'
  return 'Describe la respuesta del modelo seleccionado dentro del rango observado, manteniendo las demás entradas en sus valores actuales.'
}
