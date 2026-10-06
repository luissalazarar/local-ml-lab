import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ComparisonCriteria } from './ComparisonCriteria'

describe('ComparisonCriteria', () => {
  it('explica la referencia y los criterios concretos para MAE', () => {
    render(<ComparisonCriteria metricId="mae" problemType="regression" />)
    expect(screen.getByText(/predice siempre la mediana/)).toBeTruthy()
    expect(screen.getByText(/al menos 3 % menor que el error de la referencia/)).toBeTruthy()
    expect(screen.getByText(/al menos 6 de cada 10 pruebas/)).toBeTruthy()
    expect(screen.getByText(/a menos de 1 % del error de la referencia/)).toBeTruthy()
  })

  it('usa la clase más frecuente y umbrales absolutos en clasificación', () => {
    render(<ComparisonCriteria metricId="balanced_accuracy" problemType="classification" />)
    expect(screen.getByText(/predice siempre la clase más frecuente/)).toBeTruthy()
    expect(screen.getByText(/al menos 0,02 sobre/)).toBeTruthy()
    expect(screen.getByText(/a menos de 0,005 de diferencia/)).toBeTruthy()
  })
})
