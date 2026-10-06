import { useState } from 'react'
import type { Profile, ProfileVisualizations } from '../api/client'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 3 })

function domain(values: number[]) {
  const minimum = Math.min(...values)
  const maximum = Math.max(...values)
  const span = maximum - minimum || Math.max(Math.abs(minimum), 1)
  return { minimum, maximum, span }
}

function correlationColor(value: number | null) {
  if (value == null) return '#EEF3F3'
  const strength = Math.min(1, Math.abs(value))
  const base = value < 0 ? [217, 112, 66] : [21, 154, 146]
  const mix = base.map(channel => Math.round(255 - (255 - channel) * strength))
  return `rgb(${mix.join(',')})`
}

function Heatmap({ visuals }: { visuals: ProfileVisualizations }) {
  const names = visuals.correlation.display_names
  return <div className="correlationTable tableWrap"><table aria-label="Mapa de calor de correlaciones entre variables numéricas"><thead><tr><th>Variable</th>{names.map(name => <th key={name} title={name}>{name}</th>)}</tr></thead><tbody>{visuals.correlation.values.map((row, y) => <tr key={visuals.correlation.column_ids[y]}><th>{names[y]}</th>{row.map((value, x) => <td key={visuals.correlation.column_ids[x]} style={{ background: correlationColor(value) }} title={`${names[y]} × ${names[x]}: ${value == null ? 'No disponible' : fmt.format(value)}`}>{value == null ? '—' : fmt.format(value)}</td>)}</tr>)}</tbody></table></div>
}

function Scatterplot({ plot }: { plot: ProfileVisualizations['scatterplots'][number] }) {
  const xDomain = domain(plot.points.map(point => point[0]))
  const yDomain = domain(plot.points.map(point => point[1]))
  const x = (value: number) => 82 + ((value - xDomain.minimum) / xDomain.span) * 493
  const y = (value: number) => 292 - ((value - yDomain.minimum) / yDomain.span) * 240
  return <svg className="explorationSvg" viewBox="0 0 650 350" role="img" aria-label={`Dispersión de ${plot.x_display_name} frente a ${plot.y_display_name}`}>
    <line x1="82" y1="52" x2="82" y2="292" className="chartGrid strongGrid" />
    <line x1="82" y1="292" x2="575" y2="292" className="chartGrid strongGrid" />
    {plot.points.map(([xValue, yValue], index) => <circle key={index} cx={x(xValue)} cy={y(yValue)} r="3.8" className="chartPoint" aria-hidden="true"><title>{`${plot.x_display_name}: ${fmt.format(xValue)}; ${plot.y_display_name}: ${fmt.format(yValue)}`}</title></circle>)}
    <text x="82" y="310" className="axisTick axisTickX">{fmt.format(xDomain.minimum)}</text><text x="575" y="310" className="axisTick axisTickX">{fmt.format(xDomain.maximum)}</text>
    <text x="74" y="296" className="axisTick">{fmt.format(yDomain.minimum)}</text><text x="74" y="56" className="axisTick">{fmt.format(yDomain.maximum)}</text>
    <text x="336" y="340" className="axisTitle">{plot.x_display_name}</text><text x="18" y="172" transform="rotate(-90 18 172)" className="axisTitle">{plot.y_display_name}</text>
  </svg>
}

function Boxplots({ visuals }: { visuals: ProfileVisualizations }) {
  return <div className="boxplots" role="img" aria-label="Boxplots de variables numéricas">{visuals.boxplots.map(item => {
    const range = item.maximum - item.minimum || Math.max(Math.abs(item.minimum), 1)
    const x = (value: number) => 55 + ((value - item.minimum) / range) * 530
    return <div className="boxplotRow" key={item.column_id}><div><strong>{item.display_name}</strong><small>{item.outlier_count.toLocaleString('es-PE')} posibles atípicos · n={item.n.toLocaleString('es-PE')}</small></div><svg viewBox="0 0 640 76" aria-hidden="true"><line x1={x(item.minimum)} y1="34" x2={x(item.maximum)} y2="34" className="boxWhisker"/><line x1={x(item.minimum)} y1="24" x2={x(item.minimum)} y2="44" className="boxWhisker"/><line x1={x(item.maximum)} y1="24" x2={x(item.maximum)} y2="44" className="boxWhisker"/><rect x={x(item.q1)} y="17" width={Math.max(2, x(item.q3)-x(item.q1))} height="34" className="boxBody"/><line x1={x(item.median)} y1="17" x2={x(item.median)} y2="51" className="boxMedian"/><text x="55" y="69" className="axisTick axisTickX">{fmt.format(item.minimum)}</text><text x="585" y="69" className="axisTick axisTickX">{fmt.format(item.maximum)}</text></svg></div>
  })}</div>
}

export function DataExploration({ profile }: { profile: Profile }) {
  const visuals = profile.visualizations
  const [scatterIndex, setScatterIndex] = useState(0)
  const activeScatter = visuals ? visuals.scatterplots[Math.min(scatterIndex, visuals.scatterplots.length - 1)] : undefined
  if (!visuals) return null
  const sampleCopy = visuals.sample_count < visuals.source_row_count
    ? `Muestra determinista de ${visuals.sample_count.toLocaleString('es-PE')} de ${visuals.source_row_count.toLocaleString('es-PE')} filas.`
    : `${visuals.sample_count.toLocaleString('es-PE')} filas analizadas.`

  return <section className="panel explorationPanel">
    <div className="panelTitle"><div><span className="sectionQuestion">Exploración visual</span><h2>Patrones, distribuciones y relaciones</h2><p>{sampleCopy} Los identificadores se excluyen y las correlaciones no demuestran causalidad.</p></div></div>
    {!visuals.boxplots.length && <div className="empty">No encontramos variables numéricas continuas adecuadas para estos gráficos. Las categorías y los identificadores se conservan en la tabla.</div>}
    {visuals.correlation.display_names.length >= 2 && <article className="visualCard"><h3>Mapa de correlaciones</h3><p>Pearson resume relaciones lineales entre pares de variables numéricas; valores cercanos a cero también pueden ocultar relaciones no lineales.</p><Heatmap visuals={visuals} /></article>}
    {activeScatter && <article className="visualCard"><div className="visualCardTitle"><div><h3>Diagrama de dispersión</h3><p>Cada punto es una fila de la muestra; mostramos primero los pares con mayor correlación absoluta.</p></div>{visuals.scatterplots.length > 1 && <label>Par mostrado<select value={scatterIndex} onChange={event => setScatterIndex(Number(event.target.value))}>{visuals.scatterplots.map((item, index) => <option key={`${item.x_column_id}-${item.y_column_id}`} value={index}>{item.x_display_name} × {item.y_display_name}</option>)}</select></label>}</div><div className="chartFact">Correlación de Pearson: <strong>{fmt.format(activeScatter.correlation)}</strong></div><Scatterplot plot={activeScatter} /></article>}
    {visuals.boxplots.length > 0 && <article className="visualCard"><h3>Boxplots de variables numéricas</h3><p>La caja muestra el 50 % central; los extremos son los últimos valores dentro de 1.5 IQR. Los posibles atípicos solo se cuentan: no se eliminan.</p><Boxplots visuals={visuals} /></article>}
    {visuals.excluded_numeric_count > 0 && <small className="visualLimit">Se muestran 12 variables numéricas como máximo; {visuals.excluded_numeric_count} adicionales siguen disponibles en la tabla.</small>}
  </section>
}
