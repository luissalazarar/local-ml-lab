import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { Profile } from '../api/client'
import { DataExploration } from './DataExploration'

afterEach(cleanup)

describe('exploración visual', () => {
  it('muestra correlación, dispersión y boxplots recibidos del backend', () => {
    const profile: Profile = {
      row_count: 4,
      column_count: 2,
      duplicate_count: 0,
      sampled: false,
      columns: [],
      visualizations: {
        sample_method: 'deterministic_stride',
        sample_count: 4,
        source_row_count: 4,
        numeric_columns: [{ column_id: 'c0001', display_name: 'Ventas' }, { column_id: 'c0002', display_name: 'Costos' }],
        correlation: { method: 'pearson', column_ids: ['c0001', 'c0002'], display_names: ['Ventas', 'Costos'], values: [[1, .8], [.8, 1]] },
        boxplots: [{ column_id: 'c0001', display_name: 'Ventas', minimum: 1, q1: 2, median: 3, q3: 4, maximum: 5, outlier_count: 1, n: 4 }],
        scatterplots: [{ x_column_id: 'c0001', x_display_name: 'Ventas', y_column_id: 'c0002', y_display_name: 'Costos', correlation: .8, points: [[1, 2], [3, 4]] }],
        excluded_numeric_count: 0,
      },
    }

    render(<DataExploration profile={profile} />)

    expect(screen.getByRole('table', { name: /Mapa de calor/ })).toBeTruthy()
    expect(screen.getByRole('img', { name: /Dispersión de Ventas/ })).toBeTruthy()
    expect(screen.getByRole('img', { name: /Boxplots/ })).toBeTruthy()
    expect(screen.getByText(/no demuestran causalidad/)).toBeTruthy()
  })
})
