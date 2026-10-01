import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api, getLiveRun, LiveCandidate, LivePrediction, LiveRun } from '../../api/client'
import { humanLabel, progressMessage } from '../../presentation/labels'

const terminal = new Set(['succeeded','succeeded_with_warnings','failed','cancelled','interrupted'])
const fmt = new Intl.NumberFormat('es-PE',{maximumFractionDigits:4})

export function Progress(){
  const {runId=''}=useParams()
  const [params]=useSearchParams()
  const jobId=params.get('job')??''
  const [live,setLive]=useState<LiveRun|null>(null)
  const [elapsed,setElapsed]=useState(0)
  const [error,setError]=useState('')
  const [follow,setFollow]=useState(true)
  const [inspected,setInspected]=useState<string|null>(null)

  useEffect(()=>{
    let stopped=false, timer:number|undefined, inFlight=false, failures=0
    async function poll(){
      if(stopped||inFlight)return
      inFlight=true
      try{
        const next=await getLiveRun(runId)
        if(next){
          setLive(next);setError('');failures=0
          if(follow&&next.active_candidate_id)setInspected(next.active_candidate_id)
          if(terminal.has(next.status)){stopped=true;return}
        }
      }catch{
        failures=Math.min(failures+1,3)
        setError('Perdimos la conexión. El análisis puede seguir ejecutándose; intentaremos recuperar la vista.')
      }finally{
        inFlight=false
        if(!stopped){
          const backoff=failures?[2000,4000,8000][failures-1]:(document.hidden?5000:1000)
          timer=window.setTimeout(poll,backoff)
        }
      }
    }
    void poll()
    const visibility=()=>{if(!stopped&&!inFlight){if(timer)window.clearTimeout(timer);void poll()}}
    document.addEventListener('visibilitychange',visibility)
    return()=>{stopped=true;if(timer)window.clearTimeout(timer);document.removeEventListener('visibilitychange',visibility)}
  },[follow,runId])

  useEffect(()=>{
    const tick=()=>setElapsed(live?.started_at?Math.max(0,Math.floor((Date.now()-new Date(live.started_at).getTime())/1000)):0)
    tick();const timer=window.setInterval(tick,1000);return()=>window.clearInterval(timer)
  },[live?.started_at])

  const activeCandidate=useMemo(()=>live?.candidates.find(item=>item.candidate_id===(inspected??live.active_candidate_id)),[inspected,live])
  const currentEvent=live?.last_events.at(-1)
  const finished=Boolean(live&&terminal.has(live.status))
  async function cancel(){await api('/jobs/'+jobId+'/cancel',{method:'POST'});setError('Cancelación solicitada. El supervisor detendrá el proceso activo y sus descendientes.')}
  function inspect(candidate:LiveCandidate){setInspected(candidate.candidate_id);setFollow(false)}
  function resumeFollow(){setFollow(true);setInspected(live?.active_candidate_id??null)}

  return <main className="progressPage liveAnalysis">
    <section className="progressHero">
      <span className="eyebrow">{finished?'EVALUACIÓN TERMINADA':'ANÁLISIS EN CURSO'}</span>
      <h1>Así estamos evaluando tu data</h1>
      <p>{finished?'La evidencia quedó congelada. Puedes revisar este recorrido o abrir el resultado completo.':'Resultados provisionales. La selección puede cambiar mientras completamos evaluaciones reales.'}</p>
    </section>
    {error&&<div className="alert warning" role="status"><strong>Conexión</strong><span>{error}</span></div>}

    <section className="panel liveContext" aria-labelledby="live-context-title">
      <div><span className="sectionQuestion">Contexto y progreso</span><h2 id="live-context-title">Qué estamos comprobando</h2></div>
      <dl className="liveFacts">
        <div><dt>Objetivo</dt><dd>{humanLabel(live?.plan_summary?.problem_type??'preparando')}</dd></div>
        <div><dt>Población</dt><dd>{live?.plan_summary?.population_count?.toLocaleString('es-PE')??'Todavía no calculada'} {live?.plan_summary?.problem_type==='forecasting'?'meses':'filas'}</dd></div>
        <div><dt>Métrica</dt><dd>{humanLabel(live?.plan_summary?.primary_metric??'Todavía no calculada')}</dd></div>
        <div><dt>Validación</dt><dd>{humanLabel(live?.plan_summary?.validation_strategy??'Diseñando')}</dd></div>
      </dl>
      <div className="liveLine"><span className={finished?'statusDot':'pulse'}/><div><strong>{progressMessage(currentEvent?.stage,currentEvent?.message_code)}</strong><small>{live?.active_candidate_id?'Candidato activo: '+candidateName(live.candidates,live.active_candidate_id):'Primero congelamos el plan; después todos los candidatos usan sus mismas particiones.'}</small></div></div>
    </section>

    <section className="liveKpis" aria-label="Indicadores del análisis">
      <Kpi label="Candidatos completados" value={live?live.counters.completed_candidates+' / '+live.counters.eligible_candidates:'Todavía no calculada'} />
      <Kpi label="Evaluaciones completadas" value={live?.counters.planned_evaluations!=null?live.counters.completed_evaluations+' / '+live.counters.planned_evaluations:'Todavía no calculada'} note="Conteo de evaluaciones, no una estimación de tiempo." />
      <Kpi label="Mejor candidato completo" value={live?.ranking[0]?.display_name??'Todavía no calculada'} note={formatScore(live?.ranking[0])} />
      <Kpi label="Tiempo y actividad" value={clock(elapsed)} note={live?.heartbeat_at?'Última actividad: '+new Date(live.heartbeat_at).toLocaleTimeString('es-PE'):'Esperando primera actividad'} />
    </section>

    <section className="panel activeEvaluation">
      <div className="panelTitle"><div><span className="sectionQuestion">Evidencia real disponible</span><h2>{activeCandidate?.display_name??'Candidato activo'}</h2><p>{live?.active_preview?'La visualización cambió al terminar una unidad real; no añadimos ajustes para animarla.':'Este ajuste continúa ejecutándose; actualizaremos sus métricas al terminar.'}</p></div><div className="followControls">{!follow&&<button className="button secondary" onClick={resumeFollow}>Volver a seguir la ejecución</button>}<span className="tag">{follow?'Siguiendo candidato activo':'Inspección manual'}</span></div></div>
      <LiveVisual problem={live?.plan_summary?.problem_type} preview={follow||inspected===live?.active_preview?.candidate_id?live?.active_preview:null}/>
    </section>

    <section className="panel liveComparison">
      <span className="sectionQuestion">Comparación y explicación</span>
      <h2>Qué está haciendo el sistema</h2>
      <p>{teachingMessage(currentEvent?.event_type,live?.plan_summary?.problem_type)}</p>
      <div className="tableWrap"><table><thead><tr><th>Candidato</th><th>Estado</th><th>Evaluaciones</th><th className="numeric">Métrica completa</th><th>Revisar</th></tr></thead><tbody>{(live?.candidates??[]).map(candidate=><tr key={candidate.candidate_id}><td><strong>{candidate.display_name??candidate.candidate_id}</strong><small>{candidateReason(candidate)}</small></td><td><span className={'tag '+candidate.status}>{humanLabel(candidate.status)}</span></td><td>{candidate.completed_unit_count??0} / {candidate.planned_unit_count??live?.plan_summary?.evaluation_unit_count??'—'}</td><td className="numeric">{candidate.primary_value==null?'Todavía no calculada':fmt.format(candidate.primary_value)}</td><td><button className="button secondary" onClick={()=>inspect(candidate)}>Inspeccionar</button></td></tr>)}</tbody></table></div>
      {live?.selection_decision&&<div className="alert info"><strong>Selección congelada</strong><span>{live.selection_decision.reason??humanLabel(live.selection_decision.reason_code??'')}</span></div>}
    </section>

    <div className="footerActions">
      {live?.result_available&&<Link className="button primary" to={'/runs/'+runId}>Ver resultado completo</Link>}
      <Link className="button secondary" to="/history">{finished?'Revisar historial':'El análisis sigue aunque salgas'}</Link>
      {!finished&&<button className="button danger" onClick={cancel} disabled={!live||!['queued','running','cancel_requested'].includes(live.status)}>Cancelar análisis</button>}
    </div>
  </main>
}

function Kpi({label,value,note}:{label:string;value:string;note?:string}){return <article><span>{label}</span><strong>{value}</strong>{note&&<small>{note}</small>}</article>}

function LiveVisual({problem,preview}:{problem?:string;preview?:LiveRun['active_preview']|null}){
  if(!preview)return <div className="liveWaiting"><span className="pulse"/><p>Esperando que termine una evaluación real. El heartbeat confirma que el trabajo continúa.</p></div>
  const primary=preview.partial_metrics?.find(metric=>metric.value!=null)
  return <div className="liveVisual"><div className="liveMetric"><span>{primary?.name??'Métrica parcial'}</span><strong>{primary?.value==null?'Todavía no calculada':fmt.format(primary.value)}</strong><small>{preview.evaluation_role==='selection_backtest'?'Prueba histórica · entrenado hasta '+(preview.training_end??'el origen indicado'):'Acumulada solo con predicciones ya persistidas.'}</small></div>{problem==='classification'?<ClassificationPreview rows={preview.predictions}/>:problem==='forecasting'?<ForecastPreview rows={preview.predictions}/>:<RegressionPreview rows={preview.predictions}/>}</div>
}

function RegressionPreview({rows}:{rows:LivePrediction[]}){
  const points=rows.filter(row=>typeof row.actual==='number'&&typeof row.predicted==='number').slice(0,2000)
  if(!points.length)return <p>Todavía no hay puntos válidos para mostrar.</p>
  const values=points.flatMap(row=>[row.actual as number,row.predicted as number]),lo=Math.min(...values),hi=Math.max(...values),span=hi-lo||1
  const x=(v:number)=>42+((v-lo)/span)*516,y=(v:number)=>238-((v-lo)/span)*196
  return <svg viewBox="0 0 600 280" role="img" aria-label="Valores reales frente a predichos de las evaluaciones completadas"><line x1={x(lo)} y1={y(lo)} x2={x(hi)} y2={y(hi)} className="chartReference"/>{points.map((row,index)=><circle key={row.row_id??index} cx={x(row.actual as number)} cy={y(row.predicted as number)} r="4" className="chartPoint"><title>{'Real '+fmt.format(row.actual as number)+', predicho '+fmt.format(row.predicted as number)}</title></circle>)}<text x="300" y="272" className="axisTitle">Real</text><text x="15" y="140" transform="rotate(-90 15 140)" className="axisTitle">Predicho</text></svg>
}

function ClassificationPreview({rows}:{rows:LivePrediction[]}){
  return <div className="tableWrap"><table><thead><tr><th>Registro</th><th>Real</th><th>Predicho</th><th>Resultado</th></tr></thead><tbody>{rows.slice(0,50).map((row,index)=><tr key={row.row_id??index}><td>{row.row_id??index+1}</td><td>{String(row.actual)}</td><td>{String(row.predicted)}</td><td>{row.actual===row.predicted?'Acierto':'Error'}</td></tr>)}</tbody></table></div>
}

function ForecastPreview({rows}:{rows:LivePrediction[]}){
  return <div><p><strong>{rows[0]?.unit_id?.replace('origin-','Prueba histórica ')}</strong> · una emisión de {rows.length} pasos; no se conecta con otros orígenes.</p><div className="tableWrap"><table><thead><tr><th>Periodo</th><th className="numeric">Real</th><th className="numeric">Predicho</th><th className="numeric">Error</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row.record_id??index}><td>{row.target_period}</td><td className="numeric">{formatValue(row.actual)}</td><td className="numeric">{formatValue(row.predicted)}</td><td className="numeric">{formatValue(row.error)}</td></tr>)}</tbody></table></div></div>
}

function candidateName(candidates:LiveCandidate[],id:string){return candidates.find(item=>item.candidate_id===id)?.display_name??id}
function formatScore(candidate?:LiveCandidate){return candidate?.primary_value==null?'Solo entran candidatos completos al ranking.':humanLabel(candidate.primary_metric_id??'métrica')+': '+fmt.format(candidate.primary_value)}
function formatValue(value:unknown){return typeof value==='number'?fmt.format(value):'—'}
function clock(seconds:number){return Math.floor(seconds/60).toString().padStart(2,'0')+':'+(seconds%60).toString().padStart(2,'0')}
function candidateReason(candidate:LiveCandidate){if(candidate.reason_code)return humanLabel(candidate.reason_code);if(candidate.candidate_id.includes('balanced'))return 'Los pesos cambian el coste de errores durante el entrenamiento; no crean observaciones.';return 'Evaluado con el plan congelado y las mismas observaciones comparables.'}
function teachingMessage(eventType?:string,problem?:string){
  if(eventType==='candidate_started')return 'Primero medimos una regla sencilla. Así sabremos si los modelos aportan algo.'
  if(eventType==='unit_started')return problem==='forecasting'?'Estamos simulando estar en esta fecha del pasado. El método solo conoce lo ocurrido hasta ese momento.':'Este modelo aprende con una parte de los datos. Después comprobamos qué predice en la parte apartada.'
  if(eventType==='selection_completed')return 'Miramos error, consistencia y complejidad. Una diferencia pequeña no basta para preferir un modelo más complejo.'
  if(eventType==='final_test_completed')return 'La elección ya está cerrada. Ahora mostramos qué ocurrió en datos que no usamos para elegir.'
  if(eventType==='forecast_ready')return 'Conservamos el método elegido y lo ajustamos con el histórico disponible para estimar los próximos meses.'
  return 'Vamos a comparar estas formas de aprender y comprobaremos sus resultados con datos que no utilizaron para ajustar ese entrenamiento.'
}
