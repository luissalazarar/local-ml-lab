import { useMemo, useState } from 'react'
import type { Prediction, Result } from '../../api/client'

const fmt = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 4 })
const pct = new Intl.NumberFormat('es-PE', { style: 'percent', maximumFractionDigits: 1 })

export function ForecastExplorer({ result }: { result: Result }) {
  const future = useMemo(
    () => result.predictions.filter(row => row.evaluation_role === 'forecast_future' && typeof row.predicted === 'number'),
    [result.predictions],
  )
  const [selectedIndex, setSelectedIndex] = useState(0)

  if (!future.length) return <section className="panel scenarioUnavailable"><span className="sectionQuestion">Probar escenarios</span><h2>No hay meses futuros para explorar</h2><p>Esta corrida no guardó predicciones futuras. Revisa el resumen de la corrida o ejecuta un pronóstico con un horizonte mayor que cero.</p></section>

  const safeIndex = Math.min(selectedIndex, future.length - 1)
  const selected = future[safeIndex]
  const diagnostic = result.forecast?.horizon_diagnostics?.find(row => row.horizon === safeIndex + 1)

  return <section className="scenarioWorkspace">
    <div className="panel scenarioIntro">
      <span className="sectionQuestion">Laboratorio interactivo</span>
      <h2>Recorre el pronóstico mes por mes</h2>
      <p>Usa el selector para revisar el horizonte que ya calculó el modelo. La proyección y los errores históricos vienen del resultado guardado: esta vista no reentrena ni recalcula la corrida.</p>
      <div className="scenarioFacts"><span><strong>{future.length}</strong> meses proyectados</span><span><strong>{result.forecast?.horizon_diagnostics?.length ?? 0}</strong> horizontes con backtesting</span></div>
      <div className="alert warning"><strong>Exploración del horizonte, no un escenario causal</strong><span>Forecasting V1 usa la fecha y la serie objetivo. No hay drivers externos que mover ni una banda de certeza inventada.</span></div>
    </div>
    <div className="scenarioLayout forecastExplorerLayout">
      <div className="panel scenarioControls">
        <h2>Mes que quieres revisar</h2>
        <p>Mueve el selector para comparar la proyección con el error que tuvo ese mismo horizonte en pruebas históricas.</p>
        <label className="scenarioControl forecastHorizonControl">
          <span>Horizonte <output>Mes +{safeIndex + 1}</output></span>
          <input aria-label="Mes del horizonte" type="range" min="1" max={future.length} step="1" value={safeIndex + 1} onChange={event => setSelectedIndex(Number(event.target.value) - 1)} />
          <small>{formatPeriod(selected.target_period)}</small>
        </label>
        <div className="forecastMonthButtons" aria-label="Meses proyectados">
          {future.map((row, index) => <button type="button" className={index === safeIndex ? 'active' : ''} onClick={() => setSelectedIndex(index)} key={String(row.record_id ?? row.target_period ?? index)}>+{index + 1}<span>{formatPeriod(row.target_period)}</span></button>)}
        </div>
      </div>
      <div className="panel scenarioOutput" aria-live="polite">
        <div className="panelTitle"><div><span className="sectionQuestion">Mes seleccionado</span><h2>{formatPeriod(selected.target_period)}</h2></div></div>
        <div className="scenarioPrediction"><span>Resultado pronosticado</span><strong>{fmt.format(Number(selected.predicted))}</strong><small>Proyección guardada por el método seleccionado.</small></div>
        <div className="forecastEvidence">
          <article><span>MAE histórico en mes +{safeIndex + 1}</span><strong>{diagnostic ? fmt.format(diagnostic.selected_mae) : 'No disponible'}</strong><small>Error absoluto medio observado en los backtests para esta distancia.</small></article>
          <article><span>Referencia sencilla</span><strong>{diagnostic ? fmt.format(diagnostic.baseline_mae) : 'No disponible'}</strong><small>{diagnostic ? comparisonText(diagnostic.relative_improvement, diagnostic.outcome) : 'No hay una comparación histórica guardada.'}</small></article>
        </div>
        <ForecastPath rows={future} selectedIndex={safeIndex} />
      </div>
    </div>
  </section>
}

function ForecastPath({ rows, selectedIndex }: { rows: Prediction[], selectedIndex: number }) {
  const values = rows.map(row => Number(row.predicted))
  let low = Math.min(...values), high = Math.max(...values)
  if (low === high) { low -= .5; high += .5 }
  const padding = Math.max((high - low) * .12, 1e-9)
  low -= padding; high += padding
  const x = (index: number) => 64 + index / Math.max(1, rows.length - 1) * 516
  const y = (value: number) => 238 - (value - low) / (high - low) * 174
  const points = values.map((value, index) => `${x(index)},${y(value)}`).join(' ')

  return <figure className="scenarioChart forecastPath"><figcaption>Trayectoria futura ya calculada</figcaption><svg viewBox="0 0 640 300" role="img" aria-label="Pronóstico futuro con el mes seleccionado resaltado"><line x1="64" y1="238" x2="580" y2="238" className="chartGrid"/><line x1="64" y1="64" x2="64" y2="238" className="chartGrid"/><polyline points={points} className="futureLine"/>{rows.map((row,index) => <g key={String(row.record_id ?? row.target_period ?? index)}><circle cx={x(index)} cy={y(values[index])} r={index === selectedIndex ? 7 : 4} className={index === selectedIndex ? 'forecastSelectedPoint' : 'forecastPoint'}><title>{`${formatPeriod(row.target_period)}: ${fmt.format(values[index])}`}</title></circle><text x={x(index)} y="263" className="axisTick axisTickX">+{index + 1}</text></g>)}<text x="54" y="68" className="axisTick">{fmt.format(high)}</text><text x="54" y="238" className="axisTick">{fmt.format(low)}</text><text x="322" y="289" className="axisTitle">Mes del horizonte</text></svg></figure>
}

function formatPeriod(period?: string) {
  if (!period) return 'Periodo no disponible'
  const match = /^(\d{4})-(\d{2})/.exec(period)
  if (!match) return period
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, 1))
  return new Intl.DateTimeFormat('es-PE', { month: 'short', year: 'numeric', timeZone: 'UTC' }).format(date)
}

function comparisonText(relativeImprovement: number | null, outcome: string) {
  if (relativeImprovement == null) return 'La diferencia relativa no pudo calcularse.'
  if (outcome === 'better') return `En estos backtests, el MAE fue ${pct.format(relativeImprovement)} menor que la referencia.`
  if (outcome === 'worse') return `En estos backtests, el MAE fue ${pct.format(Math.abs(relativeImprovement))} peor que la referencia.`
  return 'En estos backtests, el error fue similar al de la referencia.'
}
