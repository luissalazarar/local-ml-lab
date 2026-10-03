import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ScenarioMetadata } from '../../api/client'
import { ScenarioExplorer } from './ScenarioExplorer'

const metadata: ScenarioMetadata = {
  available: true,
  model_name: 'Regresión Ridge',
  target_name: 'Ventas',
  problem_type: 'regression',
  fit_row_count: 120,
  model_family: 'linear',
  training_depth: 'recommended',
  controls: [{
    column_id: 'c0001', display_name: 'Ingreso', kind: 'numeric', editable: true,
    default: 10, minimum: 0, maximum: 20, step: 1, importance_mean: .8,
  }],
}

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('ScenarioExplorer', () => {
  it('actualiza la proyección desde el backend al mover un selector', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        prediction: 42, driver_id: 'c0001', driver_name: 'Ingreso', curve_unit: 'target_unit',
        curve_shape: 'nonlinear', sensitivity_direction: 'increasing',
        curve: [{ input: 0, output: 10 }, { input: 20, output: 70 }],
        warnings: ['SCENARIO_NOT_CAUSAL'],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)
    render(<MemoryRouter><ScenarioExplorer runId="run-1" metadata={metadata} /></MemoryRouter>)

    expect(await screen.findByText('42')).toBeTruthy()
    expect(screen.getByRole('img', { name: /Curva de proyección según Ingreso/ })).toBeTruthy()
    expect(screen.getByText(/Forma no lineal · tendencia ascendente/)).toBeTruthy()
    expect(screen.getByText(/no de una línea ajustada solo para este gráfico/)).toBeTruthy()
    fireEvent.change(screen.getByRole('slider'), { target: { value: '20' } })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const request = fetchMock.mock.calls.at(-1)?.[1] as RequestInit
    expect(JSON.parse(String(request.body)).values).toEqual({ c0001: 20 })
  })

  it('explica por qué una corrida antigua necesita repetirse', () => {
    render(<MemoryRouter><ScenarioExplorer runId="run-old" /></MemoryRouter>)
    expect(screen.getByText(/Fue creada antes de incorporar esta función/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Crear una nueva corrida' })).toBeTruthy()
  })
})
