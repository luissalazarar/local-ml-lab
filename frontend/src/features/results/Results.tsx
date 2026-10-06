import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, Prediction, Result, waitJob } from '../../api/client'
import { driverBar, humanLabel, metricExplanation, metricLabel } from '../../presentation/labels'
import { concepts } from '../../education/concepts'
import { DataFlow } from '../../education/DataFlow'
import { ConceptHelp } from '../../education/ConceptHelp'
import { MetricInterpretation, metricComparisonGuide, metricValueMeaning } from '../../education/MetricInterpretation'
import { useGuidedMode } from '../../education/useGuidedMode'
import { ScenarioExplorer } from './ScenarioExplorer'
import { ForecastExplorer } from './ForecastExplorer'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 4 })
const reliabilityLabel: Record<string, string> = { high: 'ALTA', medium: 'MEDIA', low: 'BAJA', not_evaluable: 'NO EVALUABLE' }

export function Results() {
  const {guided,toggle}=useGuidedMode()
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
  const selected = result.candidates.find(candidate => (candidate.candidate_id??candidate.model_id) === (result.selection_decision?.selected_candidate_id??result.selection_decision?.model_id))
  const baseline = result.candidates.find(candidate => candidate.model_id === result.baseline_comparison?.baseline_model_id)
  const names = Object.fromEntries(result.data_quality.columns.map(column => [column.column_id, column.display_name]))
  const evaluated = primary?.n_used ?? Math.max(0, ...result.evaluation_metrics.map(metric => metric.n_used), 0)
  const reliabilityContext = result.analytical_outcome === 'exploration_only'
    ? 'Exploración sin entrenamiento ni evaluación predictiva.'
    : result.analytical_outcome === 'not_evaluable'
      ? 'No se pudo evaluar un modelo con el soporte disponible.'
      : result.final_test
        ? `${evaluated.toLocaleString('es-PE')} predicciones de selección y una prueba reservada informada por separado.`
        : `${evaluated.toLocaleString('es-PE')} predicciones evaluadas. La misma evaluación también participó en la selección.`
  const improvement = result.baseline_comparison?.observed_predictive_utility === 'practical_consistent_improvement'
  const comparable = result.analytical_outcome === 'completed' && Boolean(baseline) && primary?.value != null && baseline?.primary_value != null
  const preparedRows = result.data_preparation?.rows_analyzed ?? result.dataset_summary.row_count
  const targetAvailableRows = Math.max(0, preparedRows - (result.data_preparation?.target_missing_rows ?? 0))
  const baselineSelected = Boolean(selected&&baseline&&(selected.candidate_id??selected.model_id)===(baseline.candidate_id??baseline.model_id))
  const selectedDecision = result.selection_decision?.candidate_decisions?.find(item=>item.candidate_id===(result.selection_decision?.provisional_selected_candidate_id??result.selection_decision?.selected_candidate_id))
  const showTabularScenario = result.analytical_outcome === 'completed' && ['regression','classification'].includes(result.problem_type)
  const showForecastExplorer = result.analytical_outcome === 'completed' && result.problem_type === 'forecasting'
  const showScenario = showTabularScenario || showForecastExplorer

  return <main className="resultsPage">
    <div className="resultHeader"><div><span className="eyebrow">RESULTADO DEL ANÁLISIS</span><h1>{baselineSelected?'La referencia sencilla fue suficiente':result.problem_type === 'exploration' ? 'Exploración de la data' : 'Resultados del análisis'}</h1><p>{baselineSelected?'Los modelos aprendidos no mostraron una mejora suficientemente grande y consistente para justificar mayor complejidad. Esto no demuestra que nunca exista una relación.':selected ? `Modelo seleccionado: ${selected.display_name}, con datos no usados para entrenar cada ajuste.` : 'No fue posible o necesario entrenar modelos.'}</p></div><div className="rowActions"><button className="button secondary" onClick={toggle}>{guided?'Ver detalle técnico':'Volver al modo guiado'}</button><Link className="button secondary" to="/new">Nuevo análisis</Link></div></div>
    {result.analytical_outcome === 'not_evaluable' && <section className="alert warning notEvaluable"><div><strong>No pudimos evaluar esta configuración</strong><span>{result.reliability.reasons.map(reason => humanLabel(reason)).join(' ')}</span><span>Corrige el resultado que quieres predecir, el soporte o las variables indicadas y vuelve a revisar antes de ejecutar.</span></div><Link className="button secondary" to="/new">Volver y ajustar análisis</Link></section>}
    <section className="resultSummary">
      <article className={`reliability ${result.reliability.primary_level}`}><span>¿QUÉ TAN SÓLIDA FUE LA EVALUACIÓN?</span><strong>{reliabilityLabel[result.reliability.primary_level] ?? 'NO EVALUABLE'}</strong><p>{reliabilityContext}</p>{result.reliability.reasons.map(reason => <small key={reason}>{humanLabel(reason)} </small>)}<small>Este nivel describe la solidez de la evaluación, no una probabilidad de acierto.</small></article>
      <article className="metricHero"><span>¿QUÉ NÚMERO USAMOS PARA COMPARAR?</span><strong>{primary?.value == null ? 'No disponible' : fmt.format(primary.value)}</strong><p>{metricLabel(primary?.metric_id, primary?.name)} · {primary?.n_used ?? 0} observaciones</p><small>{metricExplanation(primary?.metric_id, primary?.unit)}</small></article>
      <article className="baseline"><span>¿APORTÓ FRENTE A UNA REGLA SENCILLA?</span><strong>{!comparable ? 'Sin comparación disponible' : improvement ? 'Mejora práctica y consistente' : 'Referencia preferida'}</strong><p>{comparable ? `${selected?.display_name ?? 'El modelo seleccionado'}: ${fmt.format(primary!.value!)}. ${baseline!.display_name}: ${fmt.format(baseline!.primary_value!)}.` : 'No existe una comparación predictiva válida para este resultado.'}</p>{comparable && <small>{result.selection_decision?.reason??'La política compara magnitud, consistencia y complejidad; no afirma significancia estadística.'}</small>}</article>
    </section>
    {result.primary_metric_id && <MetricInterpretation metricId={result.primary_metric_id} value={primary?.value} baselineValue={baseline?.primary_value} baselineName={baseline?.display_name} selectedName={selected?.display_name} outcome={result.baseline_comparison?.observed_predictive_utility} />}
    {result.drivers.length > 0 && <DriverSummary result={result} names={names} onOpenScenario={showTabularScenario ? () => setTab('scenario') : undefined} />}
    {selected&&baseline&&<section className="panel selectionSummary"><span className="sectionQuestion">Resumen final de selección</span><div className="panelTitle"><div><h2>Qué seleccionamos y qué comprobamos</h2><p>La elección se congeló antes de mirar la prueba reservada.</p></div><ConceptHelp concept="selection"/></div><dl className="selectionFacts"><div><dt>Modelo elegido</dt><dd>{selected.display_name}</dd></div><div><dt>Referencia</dt><dd>{baseline.display_name}</dd></div><div><dt>Métrica</dt><dd>{metricLabel(result.primary_metric_id)}</dd></div><div><dt>Modelo</dt><dd>{primary?.value==null?'No disponible':fmt.format(primary.value)}</dd></div><div><dt>Referencia</dt><dd>{baseline.primary_value==null?'No disponible':fmt.format(baseline.primary_value)}</dd></div><div><dt>Mejora observada</dt><dd>{selectedDecision?.joint_improvement==null?'No disponible':`${fmt.format(selectedDecision.joint_improvement*100)}%`}</dd></div><div><dt>Comparaciones ganadas</dt><dd>{selectedDecision?`${selectedDecision.won_units} de ${selectedDecision.paired_units}`:'No disponible'}</dd></div><div><dt>Confirmación</dt><dd>{result.confirmation?.status==='confirmed'?'Confirmada':result.confirmation?.status==='not_confirmed'?'No confirmada':'No ejecutada'}</dd></div><div><dt>Prueba reservada</dt><dd>{result.final_test?result.final_test.selection_improvement_repeated?'Mejora repetida':'Mejora no repetida':'No disponible'}</dd></div>{!guided&&<><div><dt>Política</dt><dd>{result.selection_decision?.policy_version??'—'}</dd></div><div><dt>ID elegido</dt><dd>{result.selection_decision?.selected_candidate_id??'—'}</dd></div></>}</dl></section>}
    <nav className="tabs" aria-label="Secciones del resultado"><button className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}>Resumen y predicciones</button><button className={tab === 'models' ? 'active' : ''} onClick={() => setTab('models')}>Modelos y validación</button><button className={tab === 'drivers' ? 'active' : ''} onClick={() => setTab('drivers')}>Variables importantes</button>{showScenario && <button className={tab === 'scenario' ? 'active' : ''} onClick={() => setTab('scenario')}>Probar escenarios</button>}<button className={tab === 'export' ? 'active' : ''} onClick={() => setTab('export')}>Exportar y explicar</button></nav>
    {tab === 'summary' && result.data_preparation && Object.keys(result.data_preparation).length > 0 && <section className="panel dataJourney"><h2>Qué pasó con tus datos</h2><DataFlow compact /><ol><li><strong>Archivo original</strong><span>{result.data_preparation.rows_input?.toLocaleString('es-PE') ?? 'No registrado'} filas</span><small>Tu archivo no fue modificado.</small></li><li><strong>Versión preparada</strong><span>{preparedRows.toLocaleString('es-PE')} filas</span><small>Representaciones confirmadas.</small></li><li><strong>Apartadas al preparar</strong><span>{(result.data_preparation.rows_quarantined??0).toLocaleString('es-PE')}</span><small>Siguen en el original.</small></li><li><strong>Elegibles para este resultado</strong><span>{targetAvailableRows.toLocaleString('es-PE')}</span><small>{result.data_preparation.target_missing_rows ?? 0} filas sin resultado conocido siguen en la versión preparada, pero no pueden entrenar ni evaluar este objetivo.</small></li><li><strong>Evaluadas</strong><span>{evaluated.toLocaleString('es-PE')}</span><small>Fuera del entrenamiento de cada ajuste.</small></li>{result.validation_plan.holdout_row_ids?.length?<li><strong>Prueba reservada</strong><span>{result.validation_plan.holdout_row_ids.length.toLocaleString('es-PE')}</span><small>No eligió el modelo.</small></li>:null}</ol></section>}
    {tab === 'summary' && <section className="resultsStack"><div className="twoCol"><div className="panel"><span className="sectionQuestion">¿Con qué número comparamos?</span><h2>Métricas de evaluación</h2><div className="metricGrid">{result.evaluation_metrics.map(metric => <article key={metric.metric_id} className={metric.metric_id === result.primary_metric_id ? 'primaryMetric' : ''}><span>{metricLabel(metric.metric_id, metric.name)}</span><strong>{metric.value == null ? 'No disponible' : fmt.format(metric.value)}</strong><small>{metric.value == null ? humanLabel(metric.reason_code) : `${metric.n_used.toLocaleString('es-PE')} observaciones · ${humanLabel(metric.unit)}`}</small><small>{metric.value == null ? metricExplanation(metric.metric_id, metric.unit) : metricValueMeaning(metric.metric_id, metric.value)}</small><small>{metric.metric_id === result.primary_metric_id ? 'La comparación con la referencia está explicada arriba.' : `${metricComparisonGuide(metric.metric_id)} Este resultado no guarda una referencia separada para esta métrica secundaria.`}</small></article>)}</div></div><aside className="panel"><h2>Límites que debes considerar</h2><ul className="plainList">{result.limitations.map(item => <li key={item}>{humanLabel(item)}</li>)}</ul></aside></div><ResultVisual result={result} /><PredictionTable result={result} /></section>}
    {tab === 'models' && <section className="panel"><span className="sectionQuestion">¿Qué formas de aprender probamos?</span><h2>Cómo se eligió el modelo</h2><p>{result.selection_decision?.reason??'Comparamos magnitud del resultado, consistencia entre pruebas y complejidad.'} Los umbrales son una política del producto, no una prueba de significancia.</p><h3>Cómo se evaluó</h3><p>{humanLabel(result.validation_plan.evidence_mode ?? result.validation_plan.strategy)}. Cada ajuste aprendió solo con su entrenamiento y todos los candidatos comparables usaron las mismas observaciones apartadas.</p><div className="tableWrap"><table><thead><tr><th>Modelo</th><th>Qué hace</th><th>Estado</th><th>Pruebas</th><th className="numeric">{metricLabel(result.primary_metric_id)}</th></tr></thead><tbody>{result.candidates.map(candidate => <tr key={candidate.model_id}><td><strong>{candidate.display_name}</strong>{!guided&&<small>{candidate.candidate_id??candidate.model_id}</small>}</td><td>{modelExplanation(candidate.model_id)}{candidate.reason_code&&<small>{humanLabel(candidate.reason_code)}</small>}</td><td><span className={`tag ${candidate.status}`}>{humanLabel(candidate.status)}</span></td><td>{candidate.completed_unit_count??0} / {candidate.planned_unit_count??'—'}</td><td className="numeric">{candidate.primary_value == null ? '—' : fmt.format(candidate.primary_value)}</td></tr>)}</tbody></table></div><div className="twoCol"><div className="alert info"><strong>Confirmación</strong><span>{result.confirmation?.status==='confirmed'?'La mejora reapareció con suficiente consistencia.':result.confirmation?.status==='not_confirmed'?'La mejora no se confirmó; conservamos la referencia.':'No se ejecutó porque no aplicaba o faltaba soporte.'}</span></div><div className="alert info"><strong>Prueba reservada</strong><span>{result.final_test?result.final_test.selection_improvement_repeated?'La mejora se repitió sin cambiar el ganador.':'La mejora no se repitió; el ganador no cambió.':'No estuvo disponible.'}</span></div></div><div className="alert info"><strong>Qué significan los límites</strong><span>{result.validation_plan.population_scope === 'independent_records' ? 'La partición aleatoria supone registros independientes. Los duplicados exactos se mantuvieron juntos; otros grupos y usos temporales tabulares siguen fuera de alcance.' : result.final_test ? 'La selección usó pruebas históricas y la prueba reservada se mostró después sin cambiar el método elegido.' : 'Las pruebas históricas también participaron en la selección; no equivalen a datos externos nuevos.'}</span></div></section>}
    {tab === 'drivers' && <Drivers result={result} names={names} />}
    {tab === 'scenario' && showTabularScenario && <ScenarioExplorer runId={result.run_id} metadata={result.scenario_explorer} />}
    {tab === 'scenario' && showForecastExplorer && <ForecastExplorer result={result} />}
    {tab === 'export' && <section className="twoCol"><div className="panel"><h2>Reportes coherentes con este resultado</h2><p>Excel y PDF nacen del snapshot inmutable. Reexportar crea archivos nuevos sin volver a entrenar.</p><button className="button primary" onClick={makeReports} disabled={exportBusy}>{exportBusy ? 'Generando…' : 'Generar Excel y PDF'}</button>{exportError && <div className="alert error" role="alert">{exportError}</div>}<div className="downloadList">{exports.map(artifact => <a key={artifact.id} className="button secondary" href={`/api/v1/artifacts/${artifact.id}/download`}>Descargar {artifact.kind.toUpperCase()}</a>)}</div></div><div className="panel"><h2>Contexto para cualquier IA</h2><p>Funciona sin OpenAI. El nivel 1 usa solo estructura y métricas, nunca filas privadas.</p><button className="button secondary" onClick={previewContext}>Preparar vista previa</button>{context && <><textarea ref={contextRef} className="context" readOnly value={context} /><button className="button primary" onClick={copyContext}>{copied ? 'Copiado' : 'Copiar análisis para IA'}</button></>}</div></section>}
  </main>
}

function DriverSummary({ result, names, onOpenScenario }: { result: Result, names: Record<string, string>, onOpenScenario?: () => void }) {
  const shown = result.drivers.slice(0, 5)
  const maxAbs = Math.max(...shown.map(driver => Math.abs(driver.importance_mean)), 1e-12)
  return <section className="panel driverSummary"><div className="panelTitle"><div><span className="sectionQuestion">Qué variables aportaron más</span><h2>Principales drivers del resultado</h2><p>Ordenados por cuánto cambió el rendimiento predictivo al alterar cada variable en validación. No indican causalidad ni, por sí solos, si hacen subir o bajar el resultado.</p></div>{onOpenScenario && <button className="button secondary" onClick={onOpenScenario}>Probar valores</button>}</div><div className="driverSummaryGrid">{shown.map((driver,index) => <article key={driver.source_column_id}><span>{index + 1}</span><div><strong>{names[driver.source_column_id] ?? driver.source_column_id}</strong><i><b style={{width:`${Math.abs(driver.importance_mean) / maxAbs * 100}%`}}/></i></div><small>{driver.importance_mean < 0 ? 'Señal inestable' : fmt.format(driver.importance_mean)}</small></article>)}</div><small>Importancia medida fuera del entrenamiento. Para ver dirección y cambios del valor proyectado, abre “Probar escenarios”.</small></section>
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
  if (result.problem_type === 'regression') return <><RegressionPlot rows={result.predictions} /><RegressionErrors result={result} /></>
  if (result.problem_type === 'classification') return <><ConfusionMatrix result={result} /><PerClassMetrics result={result} /></>
  if (result.problem_type === 'forecasting') return <><ForecastSummary result={result}/><ForecastPlot rows={result.predictions} /><ForecastHorizon result={result}/></>
  return null
}

function RegressionErrors({result}:{result:Result}){
  const histogram=result.diagnostics.error_histogram
  const median=result.evaluation_metrics.find(item=>item.metric_id==='median_absolute_error')
  const p90=result.evaluation_metrics.find(item=>item.metric_id==='p90_absolute_error')
  if(!histogram&&!median&&!p90)return null
  const max=Math.max(...(histogram?.counts??[1]),1)
  const worst=result.predictions.filter(item=>typeof item.error==='number').sort((a,b)=>Math.abs(Number(b.error))-Math.abs(Number(a.error))).slice(0,10)
  return <section className="panel"><div className="panelTitle"><div><h2>Distribución y errores grandes</h2><p>Error = predicho − real. Cero indica coincidencia.</p></div><ConceptHelp concept="p90_error"/></div><div className="miniMetrics"><article><span>Mediana del error absoluto</span><strong>{median?.value==null?'No disponible':fmt.format(median.value)}</strong></article><article><span>P90 del error absoluto</span><strong>{p90?.value==null?'No disponible':fmt.format(p90.value)}</strong><small>{p90?.value==null?'':`El 90% de los errores absolutos fue igual o menor que ${fmt.format(p90.value)}.`}</small></article></div>{histogram&&<div className="histogram" role="img" aria-label="Distribución de errores con referencia en cero">{histogram.counts.map((count,index)=><i key={index} style={{height:`${Math.max(2,count/max*100)}%`}} title={`${histogram.edges[index]} a ${histogram.edges[index+1]}: ${count}`}/>)}</div>}{worst.length>0&&<div className="tableWrap"><table><thead><tr><th>Registro</th><th className="numeric">Real</th><th className="numeric">Predicho</th><th className="numeric">Error</th></tr></thead><tbody>{worst.map((row,index)=><tr key={String(row.row_id??row.record_id??index)}><td>{String(row.row_id??row.record_id??index+1)}</td><td className="numeric">{formatPrediction(row.actual)}</td><td className="numeric">{formatPrediction(row.predicted)}</td><td className="numeric">{formatPrediction(row.error)}</td></tr>)}</tbody></table></div>}</section>
}

function PerClassMetrics({result}:{result:Result}){const rows=result.diagnostics.per_class??[];if(!rows.length)return null;return <section className="panel"><h2>Rendimiento por categoría</h2><p>Las métricas completas se conservan aunque la visualización resuma matrices con más de 20 categorías.</p><div className="tableWrap"><table><thead><tr><th>Categoría</th><th className="numeric">Soporte</th><th className="numeric">Precisión</th><th className="numeric">Recall / cobertura</th><th className="numeric">F1</th></tr></thead><tbody>{rows.map(row=><tr key={row.label}><td>{row.label}{row.support>=5&&row.recall===0&&<small>El modelo no reconoció ningún caso de esta categoría durante la evaluación.</small>}</td><td className="numeric">{row.support}</td><td className="numeric">{formatPrediction(row.precision)}</td><td className="numeric">{formatPrediction(row.recall)}</td><td className="numeric">{formatPrediction(row.f1)}</td></tr>)}</tbody></table></div></section>}

function ForecastSummary({result}:{result:Result}){const selected=result.candidates.find(candidate=>(candidate.candidate_id??candidate.model_id)===(result.selection_decision?.selected_candidate_id??result.selection_decision?.model_id)),baseline=result.candidates.find(candidate=>candidate.model_id===result.baseline_comparison?.baseline_model_id),completed=result.candidates.filter(candidate=>candidate.status==='completed').map(candidate=>candidate.display_name);return <section className="panel"><div className="selectionFacts"><div><dt>Método</dt><dd>{selected?.display_name??'No disponible'}</dd></div><div><dt>Referencia</dt><dd>{baseline?.display_name??'No disponible'}</dd></div><div><dt>Backtests</dt><dd>{selected?.completed_unit_count??'No disponible'}</dd></div><div><dt>Métrica</dt><dd>{metricLabel(result.primary_metric_id)} {selected?.primary_value==null?'':fmt.format(selected.primary_value)}</dd></div><div><dt>Horizonte</dt><dd>{result.forecast?.horizon??0} meses</dd></div></div>{selected?.model_id==='last_value'&&<div className="alert info"><strong>El método que mejor cumplió las reglas fue Último valor.</strong><span>Por eso los próximos meses mantienen el último dato observado. También se evaluaron: {completed.join(', ')}.</span></div>}{result.diagnostics.forecast_horizon_stability?.warning_code&&<div className="alert warning">Las estimaciones perdieron estabilidad a ciertos horizontes. Revisa el error histórico por mes antes de usar el pronóstico.</div>}</section>}

function ForecastHorizon({result}:{result:Result}){const rows=result.forecast?.horizon_diagnostics??[];if(!rows.length)return null;const max=Math.max(...rows.map(row=>row.selected_mae),1);return <section className="panel"><h2>Error histórico por distancia al futuro</h2><p>Cada barra usa las predicciones fuera de muestra ya existentes; no se hicieron ajustes nuevos.</p><div className="horizonBars">{rows.map(row=><div key={row.horizon}><span>Mes +{row.horizon}</span><i style={{width:`${row.selected_mae/max*100}%`}}/><strong>{fmt.format(row.selected_mae)}</strong></div>)}</div></section>}

function numericDomain(values: number[]) {
  let low = Math.min(...values), high = Math.max(...values)
  const base = high - low || Math.max(Math.abs(low), 1)
  low -= base * .08; high += base * .08
  return { low, high, span: high - low }
}
const ticks = (low: number, high: number, count = 5) => Array.from({ length: count }, (_, index) => low + ((high - low) * index) / (count - 1))
const spacedIndices = (length: number, count = 6) => {
  const size = Math.min(count, length)
  return [...new Set(Array.from({ length: size }, (_, index) => Math.round(index * (length - 1) / Math.max(size - 1, 1))))]
}

function RegressionPlot({ rows }: { rows: Prediction[] }) {
  const all = rows.filter(row => row.evaluation_role === 'selection_oof' && typeof row.actual === 'number' && typeof row.predicted === 'number')
  if (!all.length) return null
  const limit = 400, step = Math.max(1, Math.ceil(all.length / limit)), points = all.filter((_, index) => index % step === 0).slice(0, limit)
  const { low, high, span } = numericDomain(all.flatMap(row => [row.actual as number, row.predicted as number]))
  const x = (value: number) => 110 + ((value - low) / span) * 500, y = (value: number) => 276 - ((value - low) / span) * 226
  return <section className="panel chartPanel"><h2>Valores reales y predichos</h2><p>La diagonal marca coincidencia exacta. {points.length < all.length ? `Se muestran ${points.length} de ${all.length} puntos mediante una muestra determinista; las métricas usan todos los registros.` : 'Cada punto corresponde a una predicción de validación.'}</p><svg viewBox="0 0 680 330" role="img" aria-label="Gráfico de valores reales frente a predichos con ejes numéricos">{ticks(low, high).map(value => <g key={value}><line x1="110" y1={y(value)} x2="610" y2={y(value)} className="chartGrid"/><line x1={x(value)} y1="50" x2={x(value)} y2="276" className="chartGrid"/><text x="100" y={y(value) + 4} className="axisTick">{fmt.format(value)}</text><text x={x(value)} y="298" className="axisTick axisTickX">{fmt.format(value)}</text></g>)}<line x1={x(low)} y1={y(low)} x2={x(high)} y2={y(high)} className="chartReference"/>{points.map((row, index) => <circle key={String(row.row_id ?? index)} cx={x(row.actual as number)} cy={y(row.predicted as number)} r="4" className="chartPoint"><title>{`Registro ${row.row_id ?? index + 1}; real ${fmt.format(row.actual as number)}; predicho ${fmt.format(row.predicted as number)}; error ${fmt.format(Number(row.error))}`}</title></circle>)}<text x="360" y="324" className="axisTitle">Real · {humanLabel(all[0].unit)}</text><text x="24" y="165" transform="rotate(-90 24 165)" className="axisTitle">Predicho · {humanLabel(all[0].unit)}</text></svg></section>
}

function ConfusionMatrix({ result }: { result: Result }) {
  const labels = result.diagnostics.class_labels ?? [], matrix = result.diagnostics.confusion_matrix ?? []
  if (!matrix.length) return null
  const support = Object.fromEntries((result.diagnostics.class_support ?? []).map(item => [item.label, item.count]))
  const max = Math.max(...matrix.flat(), 1)
  const shown=labels.slice(0,20)
  return <section className="panel"><h2>Matriz de confusión y soporte</h2><p>Filas: categoría real. Columnas: categoría predicha. Soporte es la cantidad de casos reales de cada categoría; los conteos y las etiquetas distinguen aciertos de errores.</p>{labels.length>20&&<div className="alert info">La matriz resume 20 de {labels.length} categorías; las métricas por clase conservan todas.</div>}<div className="tableWrap"><table className="confusion"><thead><tr><th>Real \ Predicho</th>{shown.map(label => <th key={label}>{label}</th>)}<th className="numeric">Soporte real</th></tr></thead><tbody>{matrix.slice(0,20).map((row, rowIndex) => <tr key={shown[rowIndex]}><th>{shown[rowIndex]}</th>{row.slice(0,20).map((value, columnIndex) => <td key={shown[columnIndex]} className={rowIndex === columnIndex ? 'correctCell' : 'errorCell'} style={{ '--cell-strength': String(.08 + .28 * value / max) } as React.CSSProperties}><strong>{value}</strong><small>{rowIndex === columnIndex ? 'Acierto' : 'Error'}</small></td>)}<td className="numeric">{support[shown[rowIndex]] ?? 0}</td></tr>)}</tbody></table></div></section>
}

function ForecastPlot({ rows }: { rows: Prediction[] }) {
  const historicalBlocks = useMemo(() => {
    const groups = new Map<string, Prediction[]>()
    for (const row of rows.filter(item => ['selection_backtest','final_test'].includes(item.evaluation_role) && typeof item.predicted === 'number')) {
      const key = row.evaluation_role === 'final_test' ? 'final_test' : row.unit_id ?? row.origin_period ?? 'selection'
      groups.set(key, [...(groups.get(key) ?? []), row])
    }
    return [...groups.entries()]
  }, [rows])
  const [selectedBlock, setSelectedBlock] = useState('')
  const history = rows.filter(row => row.evaluation_role === 'history' && typeof row.actual === 'number')
  const future = rows.filter(row => row.evaluation_role === 'forecast_future' && typeof row.predicted === 'number')
  if (!history.length || !future.length) return null
  const defaultKey = historicalBlocks.find(([key]) => key === 'final_test')?.[0] ?? historicalBlocks.at(-1)?.[0] ?? ''
  const activeKey = historicalBlocks.some(([key]) => key === selectedBlock) ? selectedBlock : defaultKey
  const validation = historicalBlocks.find(([key]) => key === activeKey)?.[1] ?? []
  const allPeriods = [...history, ...future], values = [...history.map(row => row.actual as number), ...validation.map(row => row.predicted as number), ...future.map(row => row.predicted as number)]
  const { low, high, span } = numericDomain(values), x = (index: number) => 110 + (index / Math.max(1, allPeriods.length - 1)) * 500, y = (value: number) => 270 - ((value - low) / span) * 220
  const path = (items: Array<{ value: number, index: number }>) => items.map(item => `${x(item.index)},${y(item.value)}`).join(' ')
  const historyPoints = path(history.map((row, index) => ({ value: row.actual as number, index })))
  const futurePoints = path([{ value: history.at(-1)?.actual as number, index: history.length - 1 }, ...future.map((row, index) => ({ value: row.predicted as number, index: history.length + index }))])
  const historyIndex = new Map(history.map((row,index)=>[row.target_period,index]))
  const validationPoints = path(validation.map(row => ({ value: row.predicted as number, index: historyIndex.get(row.target_period) ?? 0 })))
  const dateTicks = new Set(spacedIndices(allPeriods.length, 6))
  const forecastStartX = x(history.length - .5)
  const forecastLabelAtEnd = forecastStartX > 480
  return <section className="panel chartPanel"><div className="panelTitle"><div><h2>Histórico, última prueba fuera de muestra y pronóstico</h2><p>La línea naranja empieza donde termina el histórico. Cada prueba histórica es una emisión separada; nunca conectamos orígenes distintos como una curva continua.</p></div>{historicalBlocks.length>1&&<label>Bloque mostrado<select value={activeKey} onChange={event=>setSelectedBlock(event.target.value)}>{historicalBlocks.map(([key],index)=><option key={key} value={key}>{key==='final_test'?'Prueba reservada':'Prueba histórica '+(index+1)+' de '+historicalBlocks.length}</option>)}</select></label>}</div><svg viewBox="0 0 680 340" role="img" aria-label="Serie mensual con escala vertical, un bloque fuera de muestra y pronóstico futuro">{ticks(low, high).map(value => <g key={value}><line x1="110" y1={y(value)} x2="610" y2={y(value)} className="chartGrid"/><text x="100" y={y(value) + 4} className="axisTick">{fmt.format(value)}</text></g>)}<line x1={forecastStartX} y1="50" x2={forecastStartX} y2="270" className="forecastStart"/><text x={forecastStartX + (forecastLabelAtEnd ? -7 : 7)} y="64" textAnchor={forecastLabelAtEnd ? 'end' : 'start'} className="forecastStartLabel">Comienza el pronóstico</text><polyline points={historyPoints} className="historyLine"/><polyline points={validationPoints} className="validationLine"/><polyline points={futurePoints} className="futureLine"/>{allPeriods.map((row, index) => dateTicks.has(index) ? <text key={`${row.target_period}-${index}`} x={x(index)} y="296" className="axisTick axisTickX">{String(row.target_period).slice(0, 7)}</text> : null)}<text x="24" y="165" transform="rotate(-90 24 165)" className="axisTitle">{humanLabel(future[0].unit)}</text></svg><div className="chartLegend"><span className="historyLegend">Histórico observado</span><span className="validationLegend">{activeKey==='final_test'?'Prueba reservada':'Prueba de selección'}</span><span className="futureLegend">Pronóstico futuro</span></div></section>
}

function Drivers({ result, names }: { result: Result, names: Record<string, string> }) {
  if (!result.drivers.length) return <section className="panel"><h2>Importancia de variables</h2><div className="empty">No se dispone de importancia de variables para este análisis.</div><div className="alert warning"><strong>Importancia no es causalidad</strong><span>La ausencia de valores no demuestra inestabilidad ni falta de relación.</span></div></section>
  const maxAbs = Math.max(...result.drivers.map(driver => Math.abs(driver.importance_mean)), 1e-12)
  return <section className="panel"><span className="sectionQuestion">¿Qué información ayudó más a predecir?</span><h2>Importancia de variables</h2><p>La escala conserva el signo y la magnitud relativa en unidades de cambio de {metricLabel(result.primary_metric_id)}. Cero permanece en el centro.</p><div className="driverList">{result.drivers.map(driver => { const bar = driverBar(driver.importance_mean, maxAbs); return <div key={driver.source_column_id}><span>{names[driver.source_column_id] ?? driver.source_column_id}</span><div className="driverScale"><i className={bar.side} style={{ width: `${bar.width}%` }} /></div><strong className="numeric">{fmt.format(driver.importance_mean)}</strong></div>})}</div><div className="driverMeaning"><p><strong>Positivo:</strong> al alterar la variable, el modelo rindió peor; parece aportar información.</p><p><strong>Cerca de cero:</strong> alterarla cambió poco el rendimiento bajo esta evaluación.</p><p><strong>Negativo:</strong> el rendimiento mejoró al alterarla; puede ser ruido, variación de muestra o una señal inestable. No significa que cause algo negativo.</p></div><div className="alert warning"><strong>Importancia no es causalidad</strong><span>Estas variables ayudaron bajo esta evaluación; no demuestra que causen el resultado.</span></div></section>
}

function formatPrediction(value: unknown) { if (value == null) return '—'; return typeof value === 'number' ? fmt.format(value) : String(value) }

function modelExplanation(modelId: string) {
  const key = modelId.startsWith('extra_trees') ? 'extra_trees' : modelId.startsWith('random_forest') ? 'random_forest' : modelId
  return concepts[key]?.short ?? 'Modelo evaluado con las mismas particiones.'
}
