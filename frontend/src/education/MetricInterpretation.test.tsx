import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricInterpretation, metricValueMeaning } from './MetricInterpretation'

describe('MetricInterpretation', () => {
  it('explica MAE en la unidad del resultado y contra una referencia real', () => {
    render(<MetricInterpretation metricId="mae" value={12.5} baselineValue={18} selectedName="Ridge" baselineName="Mediana" outcome="practical_consistent_improvement" />)
    expect(screen.getByText(/distancia absoluta promedio/)).toBeTruthy()
    expect(screen.getByText(/Ridge: 12[.,]5\. Mediana: 18/)).toBeTruthy()
    expect(screen.getByText(/mejora práctica y consistente/)).toBeTruthy()
  })

  it('no inventa un umbral cuando falta una referencia comparable', () => {
    render(<MetricInterpretation metricId="rmse" value={4.2} />)
    expect(screen.getByText(/Sin una referencia comparable/)).toBeTruthy()
    expect(screen.getByText(/no tiene un umbral universal/)).toBeTruthy()
  })

  it('interpreta R² negativo contra el promedio', () => {
    expect(metricValueMeaning('r2', -0.3)).toMatch(/peor que predecir siempre el promedio/)
  })
})
