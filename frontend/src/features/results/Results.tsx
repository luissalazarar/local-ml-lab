import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, Prediction, Result, waitJob } from '../../api/client'
import { driverBar, humanLabel, metricExplanation, metricLabel } from '../../presentation/labels'
import { concepts } from '../../education/concepts'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 4 })
const reliabilityLabel: Record<string, string> = { high: 'ALTA', medium: 'MEDIA', low: 'BAJA', not_evaluable: 'NO EVALUABLE' }

export function Results() {
  const { runId } = useParams()
  const [result, setResult] = useState<Result | null>(null)
  const [tab, setTab] = useState('summary')
  const [error, setError] = useState('')
  const [exportError, setExportError] = useState('')
  const [exportBusy, setExportBusy] = useState(false)
  const [exports, setExports] = useState<Array<{ id: string, kind: string }>>([])
  const [context, setContext] = useState('')
  const [copied, setCopied] = useState(false)
  const contextRef = useRef<HTMLTextAreaElement>(null)
  const refreshArtifacts = useCallback(async () => {
    const data = await api<{ items: Array<{ id: string, kind: string }> }>(`/runs/${runId}/artifacts`).catch(() => ({ items: [] }))
    setExports(data.items)
  }, [runId])
  useEffect(() => {
    api<Result>(`/runs/${runId}/result`).then(setResult).catch((reason: Error) => setError(reason.message))
    void refreshArtifacts()
  }, [runId, refreshArtifacts])

  async function makeReports() {
    setExportBusy(true); setExportError('')
    try {
      const job = await api<{ job_id: string }>(`/runs/${runId}/exports`, { method: 'POST', body: JSON.stringify({ formats: ['xlsx', 'pdf'] }) })
      await waitJob(job.job_id); await refreshArtifacts()
    } catch (reason) { setExportError((reason as Error).message) } finally { setExportBusy(false) }
  }
  async function previewContext() {
    try {
      const data = await api<{ content: string }>(`/runs/${runId}/ai-context/preview`, { method: 'POST', body: JSON.stringify({ privacy_level: 1, detail: 'summary', format: 'md' }) })
      setContext(data.content)
    } catch (reason) { setExportError((reason as Error).message) }
  }
  async function copyContext() {
    setCopied(false)
    try { await navigator.clipboard.writeText(context) } catch {
      contextRef.current?.focus(); contextRef.current?.select()
      if (!document.execCommand('copy')) { setExportError('No se pudo copiar automáticamente. Selecciona el texto y cópialo manualmente.'); return }
    }
    setCopied(true)
  }
  if (error) return <main><div className="alert error">{error}</div></main>
  if (!result) return <main className="center"><div className="loader" /><p>Abriendo el resultado guardado…</p></main>
  const primary = result.evaluation_metrics.find(metric => metric.metric_id === result.primary_metric_id)
  const selected = result.candidates.find(candidate => candidate.model_id === result.selection_decision?.model_id)
  const baseline = result.candidates.find(candidate => candidate.model_id === result.baseline_comparison?.baseline_model_id)
  const names = Object.fromEntries(result.data_quality.columns.map(column => [column.column_id, column.display_name]))
  const evaluated = primary?.n_used ?? Math.max(0, ...result.evaluation_metrics.map(metric => metric.n_used), 0)
  const reliabilityContext = result.analytical_outcome === 'exploration_only'
    ? 'Exploración sin entrenamiento ni evaluación predictiva.'
    : result.analytical_outcome === 'not_evaluable'
      ? 'No se pudo evaluar un modelo con el soporte disponible.'
      : `${evaluated.toLocaleString('es-PE')} observaciones evaluadas. La misma evaluación también participó en la selección.`
  const improvement = result.baseline_comparison?.observed_predictive_utility === 'better_than_baseline'
  const comparable = result.analytical_outcome === 'completed' && Boolean(baseline) && primary?.value != null && baseline?.primary_value != null

  return <main className="resultsPage">
    <div className="resultHeader"><div><span className="eyebrow">RESULTADO DEL ANÁLISIS</span><h1>{result.problem_type === 'exploration' ? 'Exploración de la data' : 'Resultados del análisis'}</h1><p>{selected ? `Modelo seleccionado: ${selected.display_name}, con datos no usados para entrenar cada ajuste.` : 'No fue posible o necesario entrenar modelos.'}</p></div><Link className="button secondary" to="/new">Nuevo análisis</Link></div>
    {result.analytical_outcome === 'not_evaluable' && <section className="alert warning notEvaluable"><div><strong>No pudimos evaluar esta configuración</strong><span>{result.reliability.reasons.map(reason => humanLabel(reason)).join(' ')}</span><span>Corrige el target, el soporte o las variables indicadas y vuelve a revisar antes de ejecutar.</span></div><Link className="button secondary" to="/new">Volver y ajustar análisis</Link></section>}
    <section className="resultSummary">
      <article className={`reliability ${result.reliability.primary_level}`}><span>¿QUÉ TAN SÓLIDA FUE LA EVALUACIÓN?</span><strong>{reliabilityLabel[result.reliability.primary_level] ?? 'NO EVALUABLE'}</strong><p>{reliabilityContext}</p>{result.reliability.reasons.map(reason => <small key={reason}>{humanLabel(reason)} </small>)}<small>Este nivel describe la solidez de la evaluación, no una probabilidad de acierto.</small></article>
      <article className="metricHero"><span>¿QUÉ NÚMERO USAMOS PARA COMPARAR?</span><strong>{primary?.value == null ? 'No disponible' : fmt.format(primary.value)}</strong><p>{metricLabel(primary?.metric_id, primary?.name)} · {primary?.n_used ?? 0} observaciones</p><small>{metricExplanation(primary?.metric_id, primary?.unit)}</small></article>
      <article className="baseline"><span>¿APORTÓ FRENTE A UNA REGLA SENCILLA?</span><strong>{!comparable ? 'Sin comparación disponible' : improvement ? 'Mejora observada' : 'Resultado similar'}</strong><p>{comparable ? `${selected?.display_name ?? 'El modelo seleccionado'}: ${fmt.format(primary!.value!)}. ${baseline!.display_name}: ${fmt.format(baseline!.primary_value!)}.` : 'No existe una comparación predictiva válida para este resultado.'}</p>{comparable && <small>Comparación con {metricLabel(result.primary_metric_id)}; no es una puntuación de utilidad nueva.</small>}</article>
    </section>
    <nav className="tabs" aria-label="Secciones del resultado"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}>Resumen y predicciones</button><button className={tab === 'models' ? 'active' : ''} onClick={() => setTab('models')}>Modelos y validación</button><button className={tab === 'drivers' ? 'active' : ''} onClick={() => setTab('drivers')}>Variables importantes</button><button className={tab === 'export' ? 'active' : ''} onClick={() => setTab('export')}>Exportar y explicar</button></nav>
    {tab === 'summary' && <section className="resultsStack"><div className="twoCol"><div className="panel"><h2>Métricas de evaluación</h2><div className="metricGrid">{result.evaluation_metrics.map(metric => <article key={metric.metric_id} className={metric.metric_id === result.primary_metric_id ? 'primaryMetric' : ''}><span>{metricLabel(metric.metric_id, metric.name)}</span><strong>{metric.value == null ? 'No disponible' : fmt.format(metric.value)}</strong><small>{metric.value == null ? humanLabel(metric.reason_code) : `${metric.n_used.toLocaleString('es-PE')} observaciones · ${humanLabel(metric.unit)}`}</small><small>{metricExplanation(metric.metric_id, metric.unit)}</small></article>)}</div></div><aside className="panel"><h2>Límites que debes considerar</h2><ul className="plainList">{result.limitations.map(item => <li key={item}>{humanLabel(item)}</li>)}</ul></aside></div><ResultVisual result={result} /><PredictionTable result={result} /></section>}
    {tab === 'models' && <section className="panel"><h2>Modelos y validación</h2><p>{humanLabel(result.validation_plan.evidence_mode ?? result.validation_plan.strategy)}. Una partición de validación contiene datos separados para evaluar cada ajuste; el ganador se eligió por la métrica configurada y los empates favorecieron menor complejidad.</p><div className="tableWrap"><table><thead><tr><th>Modelo</th><th>Qué hace</th><th>Estado</th><th className="numeric">{metricLabel(result.primary_metric_id)}</th></tr></thead><tbody>{result.candidates.map(candidate => <tr key={candidate.model_id}><td><strong>{candidate.display_name}</strong></td><td>{modelExplanation(candidate.model_id)}</td><td><span className={`tag ${candidate.status}`}>{humanLabel(candidate.status)}</span></td><td className="numeric">{candidate.primary_value == null ? '—' : fmt.format(candidate.primary_value)}</td></tr>)}</tbody></table></div><div className="alert info"><strong>Alcance</strong><span>{result.validation_plan.population_scope === 'independent_records' ? 'La partición aleatoria supone registros independientes. No admite grupos, entidades repetidas ni usos temporales tabulares.' : 'La validación mensual también participó en la selección; no es una prueba final independiente.'}</span></div></section>}
    {tab === 'drivers' && <Drivers result={result} names={names} />}
    {tab === 'export' && <section className="twoCol"><div className="panel"><h2>Reportes coherentes con este resultado</h2><p>Excel y PDF nacen del snapshot inmutable. Reexportar crea archivos nuevos sin volver a entrenar.</p><button className="button primary" onClick={makeReports} disabled={exportBusy}>{exportBusy ? 'Generando…' : 'Generar Excel y PDF'}</button>{exportError && <div className="alert error" role="alert">{exportError}</div>}<div className="downloadList">{exports.map(artifact => <a key={artifact.id} className="button secondary" href={`/api/v1/artifacts/${artifact.id}/download`}>Descargar {artifact.kind.toUpperCase()}</a>)}</div></div><div className="panel"><h2>Contexto para cualquier IA</h2><p>Funciona sin OpenAI. El nivel 1 usa solo estructura y métricas, nunca filas privadas.</p><button className="button secondary" onClick={previewContext}>Preparar vista previa</button>{context && <><textarea ref={contextRef} className="context" readOnly value={context} /><button className="button primary" onClick={copyContext}>{copied ? 'Copiado' : 'Copiar análisis para IA'}</button></>}</div></section>}
  </main>
}

function PredictionTable({ result }: { result: Result }) {
  const [page, setPage] = useState(0)
  const available = useMemo(() => result.predictions.filter(row => row.evaluation_role !== 'history'), [result.predictions])
  const pageSize = 50, pages = Math.max(1, Math.ceil(available.length / pageSize)), rows = available.slice(page * pageSize, (page + 1) * pageSize)
  if (!available.length) return null
  const classification = result.problem_type === 'classification'
  return <section className="panel"><div className="panelTitle"><div><h2>Predicciones y errores</h2><p>Mostrando {page * pageSize + 1}–{Math.min((page + 1) * pageSize, available.length)} de {available.length.toLocaleString('es-PE')}. {classification ? 'En clasificación, el resultado indica acierto o error entre categorías.' : 'Error = predicho − real. El futuro sin observación real no tiene error.'}</p></div>{pages > 1 && <div className="pagination"><button className="button secondary" onClick={() => setPage(value => Math.max(0, value - 1))} disabled={page === 0}>Anterior</button><span>Página {page + 1} de {pages}</span><button className="button secondary" onClick={() => setPage(value => Math.min(pages - 1, value + 1))} disabled={page + 1 === pages}>Siguiente</button></div>}</div><div className="tableWrap"><table><thead><tr><th>Registro o periodo</th><th>Rol</th><th className="numeric">Real</th><th className="numeric">Predicho</th><th className="numeric">{classification ? 'Resultado' : 'Error'}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.row_id ?? row.record_id ?? index)}><td>{String(row.target_period ?? row.row_id ?? row.record_id ?? index + 1)}</td><td>{humanLabel(row.evaluation_role)}</td><td className="numeric">{formatPrediction(row.actual)}</td><td className="numeric">{formatPrediction(row.predicted)}</td><td className="numeric">{classification ? (row.actual === row.predicted ? 'Acierto' : 'Error') : formatPrediction(row.error)}</td></tr>)}</tbody></table></div></section>
}

function ResultVisual({ result }: { result: Result }) {
  if (result.problem_type === 'regression') return <RegressionPlot rows={result.predictions} />
  if (result.problem_type === 'classification') return <ConfusionMatrix result={result} />
  if (result.problem_type === 'forecasting') return <ForecastPlot rows={result.predictions} />
  return null
}

function numericDomain(values: number[]) {
  let low = Math.min(...values), high = Math.max(...values)
  const base = high - low || Math.max(Math.abs(low), 1)
  low -= base * .08; high += base * .08
  return { low, high, span: high - low }
}
const ticks = (low: number, high: number, count = 5) => Array.from({ length: count }, (_, index) => low + ((high - low) * index) / (count - 1))

function RegressionPlot({ rows }: { rows: Prediction[] }) {
  const all = rows.filter(row => row.evaluation_role === 'selection_oof' && typeof row.actual === 'number' && typeof row.predicted === 'number')
  if (!all.length) return null
  const limit = 400, step = Math.max(1, Math.ceil(all.length / limit)), points = all.filter((_, index) => index % step === 0).slice(0, limit)
  const { low, high, span } = numericDomain(all.flatMap(row => [row.actual as number, row.predicted as number]))
  const x = (value: number) => 72 + ((value - low) / span) * 518, y = (value: number) => 276 - ((value - low) / span) * 226
  return <section className="panel chartPanel"><h2>Valores reales y predichos</h2><p>La diagonal marca coincidencia exacta. {points.length < all.length ? `Se muestran ${points.length} de ${all.length} puntos mediante una muestra determinista; las métricas usan todos los registros.` : 'Cada punto corresponde a una predicción de validación.'}</p><svg viewBox="0 0 640 330" role="img" aria-label="Gráfico de valores reales frente a predichos con ejes numéricos">{ticks(low, high).map(value => <g key={value}><line x1="72" y1={y(value)} x2="590" y2={y(value)} className="chartGrid"/><line x1={x(value)} y1="50" x2={x(value)} y2="276" className="chartGrid"/><text x="64" y={y(value) + 4} className="axisTick">{fmt.format(value)}</text><text x={x(value)} y="298" className="axisTick axisTickX">{fmt.format(value)}</text></g>)}<line x1={x(low)} y1={y(low)} x2={x(high)} y2={y(high)} className="chartReference"/>{points.map((row, index) => <circle key={String(row.row_id ?? index)} cx={x(row.actual as number)} cy={y(row.predicted as number)} r="4" className="chartPoint"><title>{`Registro ${row.row_id ?? index + 1}; real ${fmt.format(row.actual as number)}; predicho ${fmt.format(row.predicted as number)}; error ${fmt.format(Number(row.error))}`}</title></circle>)}<text x="330" y="324" className="axisTitle">Real · {humanLabel(all[0].unit)}</text><text x="18" y="165" transform="rotate(-90 18 165)" className="axisTitle">Predicho · {humanLabel(all[0].unit)}</text></svg></section>
}

function ConfusionMatrix({ result }: { result: Result }) {
  const labels = result.diagnostics.class_labels ?? [], matrix = result.diagnostics.confusion_matrix ?? []
  if (!matrix.length) return null
  const support = Object.fromEntries((result.diagnostics.class_support ?? []).map(item => [item.label, item.count]))
  const max = Math.max(...matrix.flat(), 1)
  return <section className="panel"><h2>Matriz de confusión y soporte</h2><p>Filas: categoría real. Columnas: categoría predicha. Soporte es la cantidad de casos reales de cada categoría; los conteos y las etiquetas distinguen aciertos de errores.</p><div className="tableWrap"><table className="confusion"><thead><tr><th>Real \ Predicho</th>{labels.map(label => <th key={label}>{label}</th>)}<th className="numeric">Soporte real</th></tr></thead><tbody>{matrix.map((row, rowIndex) => <tr key={labels[rowIndex]}><th>{labels[rowIndex]}</th>{row.map((value, columnIndex) => <td key={labels[columnIndex]} className={rowIndex === columnIndex ? 'correctCell' : 'errorCell'} style={{ '--cell-strength': String(.08 + .28 * value / max) } as React.CSSProperties}><strong>{value}</strong><small>{rowIndex === columnIndex ? 'Acierto' : 'Error'}</small></td>)}<td className="numeric">{support[labels[rowIndex]] ?? 0}</td></tr>)}</tbody></table></div></section>
}

function ForecastPlot({ rows }: { rows: Prediction[] }) {
  const history = rows.filter(row => row.evaluation_role === 'history' && typeof row.actual === 'number')
  const validation = rows.filter(row => row.evaluation_role === 'selection_validation' && typeof row.predicted === 'number')
  const future = rows.filter(row => row.evaluation_role === 'forecast_future' && typeof row.predicted === 'number')
  if (!history.length || !future.length) return null
  const allPeriods = [...history, ...future], values = [...history.map(row => row.actual as number), ...validation.map(row => row.predicted as number), ...future.map(row => row.predicted as number)]
  const { low, high, span } = numericDomain(values), x = (index: number) => 70 + (index / Math.max(1, allPeriods.length - 1)) * 520, y = (value: number) => 270 - ((value - low) / span) * 220
  const path = (items: Array<{ value: number, index: number }>) => items.map(item => `${x(item.index)},${y(item.value)}`).join(' ')
  const historyPoints = path(history.map((row, index) => ({ value: row.actual as number, index })))
  const futurePoints = path([{ value: history.at(-1)?.actual as number, index: history.length - 1 }, ...future.map((row, index) => ({ value: row.predicted as number, index: history.length + index }))])
  const validationOffset = Math.max(0, history.length - validation.length)
  const validationPoints = path(validation.map((row, index) => ({ value: row.predicted as number, index: validationOffset + index })))
  const dateStep = Math.max(1, Math.ceil(allPeriods.length / 7))
  return <section className="panel chartPanel"><h2>Histórico, validación y pronóstico</h2><p>La línea naranja empieza donde termina el histórico y representa periodos futuros sin observación real. La validación punteada participó en la selección; no es una prueba final independiente.</p><svg viewBox="0 0 640 340" role="img" aria-label="Serie mensual con escala vertical, histórico, validación y pronóstico futuro">{ticks(low, high).map(value => <g key={value}><line x1="70" y1={y(value)} x2="590" y2={y(value)} className="chartGrid"/><text x="62" y={y(value) + 4} className="axisTick">{fmt.format(value)}</text></g>)}<line x1={x(history.length - .5)} y1="50" x2={x(history.length - .5)} y2="270" className="forecastStart"/><text x={x(history.length - .5) + 6} y="64" className="forecastStartLabel">Comienza el pronóstico</text><polyline points={historyPoints} className="historyLine"/><polyline points={validationPoints} className="validationLine"/><polyline points={futurePoints} className="futureLine"/>{allPeriods.map((row, index) => index % dateStep === 0 || index === allPeriods.length - 1 ? <text key={`${row.target_period}-${index}`} x={x(index)} y="296" className="axisTick axisTickX">{String(row.target_period).slice(0, 7)}</text> : null)}<text x="18" y="165" transform="rotate(-90 18 165)" className="axisTitle">{humanLabel(future[0].unit)}</text></svg><div className="chartLegend"><span className="historyLegend">Histórico observado</span><span className="validationLegend">Validación de selección</span><span className="futureLegend">Pronóstico futuro</span></div></section>
}

function Drivers({ result, names }: { result: Result, names: Record<string, string> }) {
  if (!result.drivers.length) return <section className="panel"><h2>Importancia de variables</h2><div className="empty">No se dispone de importancia de variables para este análisis.</div><div className="alert warning"><strong>Importancia no es causalidad</strong><span>La ausencia de valores no demuestra inestabilidad ni falta de relación.</span></div></section>
  const maxAbs = Math.max(...result.drivers.map(driver => Math.abs(driver.importance_mean)), 1e-12)
  return <section className="panel"><h2>Importancia de variables</h2><p>La escala conserva el signo y la magnitud relativa en unidades de cambio de {metricLabel(result.primary_metric_id)}. Cero permanece en el centro.</p><div className="driverList">{result.drivers.map(driver => { const bar = driverBar(driver.importance_mean, maxAbs); return <div key={driver.source_column_id}><span>{names[driver.source_column_id] ?? driver.source_column_id}</span><div className="driverScale"><i className={bar.side} style={{ width: `${bar.width}%` }} /></div><strong className="numeric">{fmt.format(driver.importance_mean)}</strong></div>})}</div><div className="alert warning"><strong>Importancia no es causalidad</strong><span>Estas variables ayudaron bajo esta evaluación; no demuestra que causen el resultado.</span></div></section>
}

function formatPrediction(value: unknown) { if (value == null) return '—'; return typeof value === 'number' ? fmt.format(value) : String(value) }

function modelExplanation(modelId: string) {
  const key = modelId.startsWith('extra_trees') ? 'extra_trees' : modelId.startsWith('random_forest') ? 'random_forest' : modelId
  return concepts[key]?.short ?? 'Modelo evaluado con las mismas particiones.'
}
