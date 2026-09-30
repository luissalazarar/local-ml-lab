import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, Prediction, Result, waitJob } from '../../api/client'

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
    setExportBusy(true)
    setExportError('')
    try {
      const job = await api<{ job_id: string }>(`/runs/${runId}/exports`, { method: 'POST', body: JSON.stringify({ formats: ['xlsx', 'pdf'] }) })
      await waitJob(job.job_id)
      await refreshArtifacts()
    } catch (reason) {
      setExportError((reason as Error).message)
    } finally {
      setExportBusy(false)
    }
  }
  async function previewContext() {
    try {
      const data = await api<{ content: string }>(`/runs/${runId}/ai-context/preview`, { method: 'POST', body: JSON.stringify({ privacy_level: 1, detail: 'summary', format: 'md' }) })
      setContext(data.content)
    } catch (reason) {
      setExportError((reason as Error).message)
    }
  }
  async function copyContext() {
    setCopied(false)
    try {
      await navigator.clipboard.writeText(context)
    } catch {
      contextRef.current?.focus()
      contextRef.current?.select()
      if (!document.execCommand('copy')) {
        setExportError('No se pudo copiar automáticamente. Selecciona el texto y cópialo manualmente.')
        return
      }
    }
    setCopied(true)
  }
  if (error) return <main><div className="alert error">{error}</div></main>
  if (!result) return <main className="center"><div className="loader" /><p>Abriendo resultado inmutable…</p></main>
  const primary = result.evaluation_metrics.find(metric => metric.metric_id === result.primary_metric_id)
  const names = Object.fromEntries(result.data_quality.columns.map(column => [column.column_id, column.display_name]))
  return <main className="resultsPage">
    <div className="resultHeader"><div><span className="eyebrow">RESULTADO DEL ANÁLISIS</span><h1>{result.problem_type === 'exploration' ? 'Exploración de la data' : 'Lo que encontramos en tu data'}</h1><p>{result.selection_decision ? `Seleccionamos ${result.selection_decision.model_id} usando evidencia comparable fuera de train.` : 'No fue posible o necesario entrenar modelos.'}</p></div><Link className="button secondary" to="/new">Nuevo análisis</Link></div>
    <section className="resultSummary"><article className={`reliability ${result.reliability.primary_level}`}><span>CONFIABILIDAD DEL ANÁLISIS</span><strong>{reliabilityLabel[result.reliability.primary_level] ?? 'NO EVALUABLE'}</strong><p>Solidez de la evaluación</p><small>No es una probabilidad de acierto.</small></article><article className="metricHero"><span>MÉTRICA PRINCIPAL</span><strong>{primary?.value == null ? 'No disponible' : fmt.format(primary.value)}</strong><p>{primary?.name ?? 'Sin métrica predictiva'} · {primary?.n_used ?? 0} observaciones</p><small>{primary?.unit === 'target_unit' ? 'En la unidad real del objetivo.' : 'Score de evaluación; no es una probabilidad.'}</small></article><article className="baseline"><span>FRENTE A LA REFERENCIA</span><strong>{result.baseline_comparison?.observed_predictive_utility === 'better_than_baseline' ? 'Mejora observada' : 'Resultado similar'}</strong><p>Una referencia sencilla puede ser el mejor resultado.</p></article></section>
    <nav className="tabs" aria-label="Secciones del resultado"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}>Resumen y predicciones</button><button className={tab === 'models' ? 'active' : ''} onClick={() => setTab('models')}>Modelos y validación</button><button className={tab === 'drivers' ? 'active' : ''} onClick={() => setTab('drivers')}>Variables importantes</button><button className={tab === 'export' ? 'active' : ''} onClick={() => setTab('export')}>Exportar y explicar</button></nav>
    {tab === 'summary' && <section className="resultsStack"><div className="twoCol"><div className="panel"><h2>Métricas de evaluación</h2><div className="metricGrid">{result.evaluation_metrics.map(metric => <article key={metric.metric_id} className={metric.metric_id === result.primary_metric_id ? 'primaryMetric' : ''}><span>{metric.name}</span><strong>{metric.value == null ? 'No disponible' : fmt.format(metric.value)}</strong><small>{metric.value == null ? metric.reason_code : `${metric.n_used} observaciones · ${metric.unit}`}</small></article>)}</div></div><aside className="panel"><h2>Límites que debes considerar</h2><ul className="plainList">{result.limitations.map(item => <li key={item}>{item}</li>)}</ul></aside></div><ResultVisual result={result} /><PredictionTable result={result} /></section>}
    {tab === 'models' && <section className="panel"><h2>Todos los modelos probados</h2><div className="tableWrap"><table><thead><tr><th>Modelo</th><th>Estado</th><th>{result.primary_metric_id}</th></tr></thead><tbody>{result.candidates.map(candidate => <tr key={candidate.model_id}><td><strong>{candidate.display_name}</strong><small>{candidate.model_id}</small></td><td><span className={`tag ${candidate.status}`}>{candidate.status}</span></td><td>{candidate.primary_value == null ? '—' : fmt.format(candidate.primary_value)}</td></tr>)}</tbody></table></div><div className="alert info"><strong>Alcance</strong><span>{result.validation_plan.population_scope === 'independent_records' ? 'La partición aleatoria supone registros independientes. No admite grupos, entidades repetidas ni predicción temporal tabular.' : 'El bloque mensual reservado también participó en la selección; no es una prueba final independiente.'}</span></div></section>}
    {tab === 'drivers' && <section className="panel"><h2>Variables que ayudaron a predecir</h2><p>Permutation importance se calculó sobre los folds donde cada modelo no fue ajustado. Esa validación también participó en la selección.</p>{result.drivers.length ? <div className="driverList">{result.drivers.map((driver, index) => <div key={driver.source_column_id}><span>{index + 1}. {names[driver.source_column_id] ?? driver.source_column_id}</span><div><i style={{ width: `${Math.max(2, Math.min(100, Math.abs(driver.importance_mean) * 100))}%` }} /></div><strong>{fmt.format(driver.importance_mean)}</strong></div>)}</div> : <div className="empty">No hubo evidencia suficiente para una explicación estable.</div>}<div className="alert warning"><strong>Importancia no es causalidad</strong><span>Estas variables ayudaron bajo esta evaluación; no demuestra que causen el resultado.</span></div></section>}
    {tab === 'export' && <section className="twoCol"><div className="panel"><h2>Reportes coherentes con este resultado</h2><p>Excel y PDF nacen del snapshot inmutable. Cada exportación tiene identidad y archivo propios.</p><button className="button primary" onClick={makeReports} disabled={exportBusy}>{exportBusy ? 'Generando…' : 'Generar Excel y PDF'}</button>{exportError && <div className="alert error" role="alert">{exportError}</div>}<div className="downloadList">{exports.map(artifact => <a key={artifact.id} className="button secondary" href={`/api/v1/artifacts/${artifact.id}/download`}>Descargar {artifact.kind.toUpperCase()}</a>)}</div></div><div className="panel"><h2>Contexto para cualquier IA</h2><p>Funciona sin OpenAI. Nivel 1 usa solo estructura y métricas, nunca filas privadas.</p><button className="button secondary" onClick={previewContext}>Preparar vista previa</button>{context && <><textarea ref={contextRef} className="context" readOnly value={context} /><button className="button primary" onClick={copyContext}>{copied ? 'Copiado' : 'Copiar análisis para IA'}</button></>}</div></section>}
  </main>
}

function PredictionTable({ result }: { result: Result }) {
  const rows = result.predictions.filter(row => row.evaluation_role !== 'history').slice(0, 50)
  if (!rows.length) return null
  return <section className="panel"><h2>Predicciones y errores</h2><p>Se muestran hasta 50 filas. Los errores numéricos están en la unidad del objetivo.</p><div className="tableWrap"><table><thead><tr><th>Registro / periodo</th><th>Rol</th><th>Real</th><th>Predicho</th><th>Error</th></tr></thead><tbody>{rows.map((row, index) => <tr key={String(row.row_id ?? row.record_id ?? index)}><td>{String(row.target_period ?? row.row_id ?? row.record_id ?? index + 1)}</td><td>{row.evaluation_role}</td><td>{formatPrediction(row.actual)}</td><td>{formatPrediction(row.predicted)}</td><td>{formatPrediction(row.error)}</td></tr>)}</tbody></table></div></section>
}

function ResultVisual({ result }: { result: Result }) {
  if (result.problem_type === 'regression') return <RegressionPlot rows={result.predictions} />
  if (result.problem_type === 'classification') return <ConfusionMatrix result={result} />
  if (result.problem_type === 'forecasting') return <ForecastPlot rows={result.predictions} />
  return null
}

function RegressionPlot({ rows }: { rows: Prediction[] }) {
  const points = rows.filter(row => typeof row.actual === 'number' && typeof row.predicted === 'number')
  if (!points.length) return null
  const values = points.flatMap(row => [row.actual as number, row.predicted as number])
  const low = Math.min(...values), high = Math.max(...values), span = high - low || 1
  return <section className="panel chartPanel"><h2>Real frente a predicho</h2><p>Cada punto es una predicción fuera del train de su fold. La diagonal representa coincidencia perfecta.</p><svg viewBox="0 0 640 320" role="img" aria-label="Gráfico de valores reales frente a predichos"><line x1="55" y1="270" x2="600" y2="25" className="chartReference" />{points.map((row, index) => <circle key={index} cx={55 + (((row.actual as number) - low) / span) * 545} cy={270 - (((row.predicted as number) - low) / span) * 245} r="4" className="chartPoint" />)}<text x="280" y="310">Real</text><text x="18" y="165" transform="rotate(-90 18 165)">Predicho</text></svg></section>
}

function ConfusionMatrix({ result }: { result: Result }) {
  const labels = result.diagnostics.class_labels ?? []
  const matrix = result.diagnostics.confusion_matrix ?? []
  if (!matrix.length) return null
  const support = Object.fromEntries((result.diagnostics.class_support ?? []).map(item => [item.label, item.count]))
  return <section className="panel"><h2>Matriz de confusión y soporte</h2><p>Filas: clase real. Columnas: clase predicha. Evaluación fuera de train.</p><div className="tableWrap"><table className="confusion"><thead><tr><th>Real \ Predicho</th>{labels.map(label => <th key={label}>{label}</th>)}<th>Soporte real</th></tr></thead><tbody>{matrix.map((row, rowIndex) => <tr key={labels[rowIndex]}><th>{labels[rowIndex]}</th>{row.map((value, columnIndex) => <td key={labels[columnIndex]} className={rowIndex === columnIndex ? 'correctCell' : ''}>{value}</td>)}<td>{support[labels[rowIndex]] ?? 0}</td></tr>)}</tbody></table></div></section>
}

function ForecastPlot({ rows }: { rows: Prediction[] }) {
  const history = rows.filter(row => row.evaluation_role === 'history')
  const future = rows.filter(row => row.evaluation_role === 'forecast_future')
  const all = [...history.map(row => ({ ...row, value: row.actual as number })), ...future.map(row => ({ ...row, value: row.predicted as number }))]
  if (!history.length || !future.length) return null
  const values = all.map(row => row.value), low = Math.min(...values), high = Math.max(...values), span = high - low || 1
  const point = (value: number, index: number) => `${45 + (index / Math.max(1, all.length - 1)) * 555},${270 - ((value - low) / span) * 225}`
  const historyPoints = history.map((row, index) => point(row.actual as number, index)).join(' ')
  const futurePoints = [{ value: history.at(-1)?.actual as number }, ...future.map(row => ({ value: row.predicted as number }))].map((row, index) => point(row.value, history.length - 1 + index)).join(' ')
  return <section className="panel chartPanel"><h2>Historia y pronóstico futuro</h2><p>Serie mensual regular. Naranja indica periodos futuros sin valor real conocido; no se inventan bandas.</p><svg viewBox="0 0 640 320" role="img" aria-label="Historia mensual y pronóstico futuro"><polyline points={historyPoints} className="historyLine" /><polyline points={futurePoints} className="futureLine" />{future.map((row, index) => <text key={String(row.target_period)} x={45 + ((history.length + index) / Math.max(1, all.length - 1)) * 555} y="300" className="axisLabel">{String(row.target_period).slice(0, 7)}</text>)}</svg><div className="chartLegend"><span className="historyLegend">Historia</span><span className="futureLegend">Pronóstico futuro</span></div></section>
}

function formatPrediction(value: unknown) {
  if (value == null) return '—'
  return typeof value === 'number' ? fmt.format(value) : String(value)
}
