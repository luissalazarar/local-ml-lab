import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Result } from '../../api/client'
import { ForecastExplorer } from './ForecastExplorer'

const result = {
  problem_type: 'forecasting',
  predictions: [
    { record_id: 'future-01', evaluation_role: 'forecast_future', predicted: 120, target_period: '2026-01-01' },
    { record_id: 'future-02', evaluation_role: 'forecast_future', predicted: 145, target_period: '2026-02-01' },
  ],
  forecast: {
    horizon: 2,
    horizon_diagnostics: [
      { horizon: 1, selected_mae: 10, baseline_mae: 20, relative_improvement: .5, outcome: 'better' },
      { horizon: 2, selected_mae: 12, baseline_mae: 16, relative_improvement: .25, outcome: 'better' },
    ],
  },
} as unknown as Result

afterEach(cleanup)

describe('ForecastExplorer', () => {
  it('recorre las predicciones guardadas y muestra evidencia del horizonte', () => {
    render(<ForecastExplorer result={result} />)

    expect(screen.getByRole('heading', { name: /ene.*2026/i })).toBeTruthy()
    expect(screen.getByText('120')).toBeTruthy()
    expect(screen.getByText('10')).toBeTruthy()
    fireEvent.change(screen.getByRole('slider', { name: 'Mes del horizonte' }), { target: { value: '2' } })
    expect(screen.getByRole('heading', { name: /feb.*2026/i })).toBeTruthy()
    expect(screen.getByText('145')).toBeTruthy()
    expect(screen.getByText('12')).toBeTruthy()
    expect(screen.getByText(/no reentrena ni recalcula/i)).toBeTruthy()
    expect(screen.getByRole('img', { name: /mes seleccionado resaltado/i })).toBeTruthy()
  })
})
