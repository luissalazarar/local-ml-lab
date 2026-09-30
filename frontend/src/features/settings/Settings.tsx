import { useCallback, useEffect, useState } from 'react'
import { api } from '../../api/client'

type System = { name: string, version: string, api: string, queue: string, worker: string, can_accept_jobs: boolean, limits: Record<string, number>, capabilities: Record<string, boolean>, openai: { configured: boolean } }
type Dataset = { id: string, original_filename: string, size_bytes: number, status: string, created_at: string }

export function Settings() {
  const [system, setSystem] = useState<System | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    const [status, stored] = await Promise.all([api<System>('/system'), api<{ items: Dataset[] }>('/datasets')])
    setSystem(status)
    setDatasets(stored.items)
  }, [])
  useEffect(() => { void load().catch((reason: Error) => setError(reason.message)) }, [load])
  async function remove(dataset: Dataset) {
    if (!window.confirm(`Eliminar permanentemente “${dataset.original_filename}”? Solo se permite si no conserva análisis.`)) return
    try {
      await api(`/datasets/${dataset.id}`, { method: 'DELETE' })
      await load()
    } catch (reason) {
      setError((reason as Error).message)
    }
  }
  return <main><div className="pageTitle"><div><span className="eyebrow">ESTADO LOCAL</span><h1>Servicios, límites y datos</h1><p>Diagnóstico seguro, sin rutas internas ni secretos.</p></div></div>{error && <div className="alert error" role="alert">{error}</div>}{system ? <><section className="serviceGrid">{[['API', system.api], ['Cola', system.queue], ['Worker', system.worker]].map(([name, state]) => <article className="panel" key={name}><span className={`statusDot ${state}`} /><div><strong>{name}</strong><small>{state === 'ready' ? 'Disponible' : 'No disponible'}</small></div></article>)}</section><section className="twoCol"><div className="panel"><h2>Capacidades</h2><ul className="checkList">{Object.entries(system.capabilities).map(([key, available]) => <li key={key}><span>{available ? '✓' : '—'}</span>{key}</li>)}</ul></div><div className="panel"><h2>Límites visibles</h2><dl className="reviewList">{Object.entries(system.limits).map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value.toLocaleString('es-PE')}</dd></div>)}</dl><p className="muted">Versión {system.version}</p></div></section><section className="panel dataManager"><h2>Datasets locales</h2><p>La eliminación se bloquea si el dataset conserva análisis o trabajos activos.</p>{datasets.length ? <div className="tableWrap"><table><thead><tr><th>Archivo</th><th>Estado</th><th>Tamaño</th><th /></tr></thead><tbody>{datasets.map(dataset => <tr key={dataset.id}><td><strong>{dataset.original_filename}</strong><small>{dataset.id.slice(0, 8)}</small></td><td>{dataset.status}</td><td>{(dataset.size_bytes / 1024).toLocaleString('es-PE', { maximumFractionDigits: 1 })} KiB</td><td><button className="linkDanger" onClick={() => void remove(dataset)}>Eliminar</button></td></tr>)}</tbody></table></div> : <div className="empty">No hay datasets guardados.</div>}</section></> : <div className="loader" />}</main>
}
