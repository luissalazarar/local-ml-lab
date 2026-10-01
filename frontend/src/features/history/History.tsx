import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, Run } from '../../api/client'
import { humanLabel } from '../../presentation/labels'

export function History() {
  const [runs, setRuns] = useState<Run[]>([])
  const [error, setError] = useState('')
  const load = useCallback(() => api<{ items: Run[] }>('/runs').then(data => setRuns(data.items)).catch((reason: Error) => setError(reason.message)), [])
  useEffect(() => { void load() }, [load])
  async function remove(run: Run) {
    if (!window.confirm(`Eliminar de forma permanente el análisis “${run.display_name}” y sus exportaciones locales?`)) return
    try {
      await api(`/runs/${run.id}`, { method: 'DELETE' })
      await load()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }
  return <main>
    <div className="pageTitle"><div><span className="eyebrow">HISTORIAL LOCAL</span><h1>Tus análisis</h1><p>Los resultados permanecen en este equipo y se abren sin volver a entrenar.</p></div><Link className="button primary" to="/new">Nuevo análisis</Link></div>
    {error && <div className="alert error" role="alert">{error}</div>}
    <section className="panel">{runs.length ? <div className="tableWrap"><table><thead><tr><th>Nombre y dataset</th><th>Objetivo y resultado</th><th>Modelo y referencia</th><th>Estado</th><th>Fecha</th><th>Acciones</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}>
      <td><strong>{run.display_name}</strong><small>{run.dataset_original_name??'Dataset local'}</small>{run.dataset_version_kind === 'prepared' && <small>Versión preparada · {run.preparation_summary?.transformations?.length ?? 0} transformaciones · {run.preparation_summary?.rows_quarantined ?? 0} filas apartadas</small>}</td>
      <td>{humanLabel(run.goal)}<small>{run.result_summary??'Resultado todavía no disponible'}</small></td><td><strong>{run.selected_model_name??'—'}</strong><small>Referencia: {run.baseline_model_name??'—'}</small></td><td><span className={`tag ${run.status}`}>{humanLabel(run.status)}</span></td>
      <td>{new Intl.DateTimeFormat('es-PE', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(run.created_at))}</td>
      <td><div className="rowActions">{run.dataset_version_kind === 'prepared' && run.dataset_version_id ? <a href={`/api/v1/dataset-versions/${run.dataset_version_id}/recipe/download`}>Ver preparación</a> : null}{run.result_available ? <><Link to={`/runs/${run.id}`}>Abrir</Link><Link to={`/runs/${run.id}/progress?job=${run.latest_job_id??''}`}>Revisar cómo se obtuvo</Link></> : run.latest_job_id ? <Link to={`/runs/${run.id}/progress?job=${run.latest_job_id}`}>Ver progreso</Link> : null}<button className="linkDanger" onClick={() => void remove(run)} disabled={['queued', 'running', 'cancel_requested'].includes(run.status)}>Eliminar</button></div></td>
    </tr>)}</tbody></table></div> : <div className="empty"><h2>Aún no hay análisis</h2><p>Prueba con uno de los ejemplos sintéticos para conocer el flujo.</p><Link className="button primary" to="/new">Comenzar</Link></div>}</section>
  </main>
}
