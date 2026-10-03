import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'
import { useGuidedMode } from '../../education/useGuidedMode'
import { humanLabel } from '../../presentation/labels'

type System = { name: string, version: string, display_version: string, api: string, queue: string, worker: string, can_accept_jobs: boolean, limits: Record<string, number>, capabilities: Record<string, boolean>, openai: { configured: boolean }, analytical_engine?:{version:string;selection_policy:string;analysis_plan_version:string;forecast_methods_count:number;tabular_candidates_count:number;catalog?:unknown} }
type Dataset = { id: string, original_filename: string, size_bytes: number, status: string, created_at: string }

export function Settings() {
  const { guided, toggle } = useGuidedMode()
  const [system, setSystem] = useState<System | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [deletingAll, setDeletingAll] = useState(false)
  const load = useCallback(async () => {
    const [status, stored] = await Promise.all([
      api<System>('/system'),
      api<{ items: Dataset[] }>('/datasets'),
    ])
    setSystem(status)
    setDatasets(stored.items)
  }, [])
  useEffect(() => { void load().catch((reason: Error) => setError(reason.message)) }, [load])

  async function remove(dataset: Dataset) {
    if (!window.confirm(`Eliminar permanentemente “${dataset.original_filename}”? Solo se permite si no conserva análisis.`)) return
    try {
      setError('')
      setNotice('')
      await api(`/datasets/${dataset.id}`, { method: 'DELETE' })
      await load()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }

  async function removeAll() {
    const confirmed = window.confirm('¿Borrar todos los archivos, versiones preparadas, corridas, reportes e historial guardados? La aplicación y su configuración se conservarán. Esta acción no se puede deshacer.')
    if (!confirmed) return
    setDeletingAll(true)
    setError('')
    setNotice('')
    try {
      await api('/local-data', { method: 'DELETE' })
      setDatasets([])
      setNotice('Se borraron los datos guardados. La aplicación y su configuración siguen intactas.')
    } catch (reason) {
      setError((reason as Error).message)
    } finally {
      setDeletingAll(false)
    }
  }

  return <main>
    <div className="pageTitle"><div><span className="eyebrow">ESTADO LOCAL</span><h1>Servicios, límites y datos</h1><p>Diagnóstico seguro, sin rutas internas ni secretos.</p></div></div>
    {error && <div className="alert error" role="alert">{error}</div>}
    {notice && <div className="alert success" role="status">{notice}</div>}
    {system ? <>
      <section className="panel versionPanel"><span>Versión de Laboratorio ML</span><strong>v{system.display_version}</strong><small>API y frontend/release: {system.version}</small></section>
      <section className="serviceGrid">{[['API', system.api], ['Cola', system.queue], ['Worker', system.worker]].map(([name, state]) => <article className="panel" key={name}><span className={`statusDot ${state}`} /><div><strong>{name}</strong><small>{humanLabel(state, 'No disponible')}</small></div></article>)}</section>
      {system.analytical_engine && <section className="panel"><div className="panelTitle"><div><span className="sectionQuestion">Motor analítico</span><h2>Configuración verificable</h2><p>{system.analytical_engine.tabular_candidates_count} candidatos tabulares y {system.analytical_engine.forecast_methods_count} métodos de pronóstico disponibles.</p></div><button className="button secondary" onClick={toggle}>{guided ? 'Ver detalle técnico' : 'Ocultar detalle técnico'}</button></div><dl className="reviewList"><div><dt>Versión</dt><dd>{system.analytical_engine.version}</dd></div>{!guided && <><div><dt>Política de selección</dt><dd>{system.analytical_engine.selection_policy}</dd></div><div><dt>Versión del plan</dt><dd>{system.analytical_engine.analysis_plan_version}</dd></div></>}</dl></section>}
      <section className="twoCol"><div className="panel"><h2>Capacidades</h2><ul className="checkList">{Object.entries(system.capabilities).map(([key, available]) => <li key={key}><span>{available ? '✓' : '—'}</span>{humanLabel(key)}</li>)}</ul></div><div className="panel"><h2>Límites visibles</h2><dl className="reviewList">{Object.entries(system.limits).map(([key, value]) => <div key={key}><dt>{humanLabel(key)}</dt><dd>{value.toLocaleString('es-PE')}</dd></div>)}</dl></div></section>
      <section className="panel dataManager"><h2>Datasets locales</h2><p>La eliminación se bloquea si el dataset conserva análisis o trabajos activos.</p>{datasets.length ? <div className="tableWrap"><table><thead><tr><th>Archivo</th><th>Estado</th><th className="numeric">Tamaño</th><th /></tr></thead><tbody>{datasets.map(dataset => <tr key={dataset.id}><td><strong>{dataset.original_filename}</strong><small>{dataset.id.slice(0, 8)}</small></td><td>{humanLabel(dataset.status)}</td><td className="numeric">{(dataset.size_bytes / 1024).toLocaleString('es-PE', { maximumFractionDigits: 1 })} KiB</td><td><button className="linkDanger" onClick={() => void remove(dataset)}>Eliminar</button></td></tr>)}</tbody></table></div> : <div className="empty">No hay datasets guardados.</div>}</section>
      <section className="panel dangerZone"><div><span className="sectionQuestion">Limpieza segura</span><h2>Borrar todos los datos guardados</h2><p>Elimina uploads, versiones preparadas, corridas, reportes e historial. Conserva la aplicación, su configuración, la base de datos y la estructura necesaria para seguir usándola.</p><small>Si hay una importación o un trabajo activo, el borrado se bloquea para evitar datos incompletos.</small></div><button className="button danger" onClick={() => void removeAll()} disabled={deletingAll}>{deletingAll ? 'Borrando…' : 'Borrar datos guardados'}</button></section>
    </> : <div className="loader" />}
  </main>
}
