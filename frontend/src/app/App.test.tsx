import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Home } from '../features/home/Home'
import { App } from './App'
import { driverBar, humanLabel, metricExplanation, metricLabel } from '../presentation/labels'

afterEach(() => vi.restoreAllMocks())

describe('contrato básico', () => {
  it('presenta la acción principal sin jerga técnica', () => {
    render(<MemoryRouter><Home /></MemoryRouter>)
    expect(screen.getByRole('link', {name: 'Analizar mi archivo'})).toBeTruthy()
    expect(screen.getByText(/Tus datos se procesan en este equipo/)).toBeTruthy()
    expect(screen.getByText(/Sin GPU obligatoria/)).toBeTruthy()
    expect(screen.getByText(/sin meses faltantes/i)).toBeTruthy()
  })

  it('presenta marca y autoría como enlaces independientes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ csrf_token: 'test' }) }))
    render(<MemoryRouter><App /></MemoryRouter>)
    await waitFor(() => expect(screen.getByRole('link', { name: 'Laboratorio ML' })).toBeTruthy())
    const author = screen.getByRole('link', { name: /Desarrollado por Luis Salazar/ })
    expect(author.getAttribute('href')).toBe('https://www.linkedin.com/in/luissalazarar/')
    expect(author.getAttribute('target')).toBe('_blank')
    expect(author.getAttribute('rel')).toBe('noopener noreferrer')
    expect(screen.getByRole('link', { name: 'Laboratorio ML' }).contains(author)).toBe(false)
    const brand = screen.getByRole('link', { name: 'Laboratorio ML' })
    expect(brand.textContent).toBe('Laboratorio ML')
    expect(brand.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true')
    expect(author.contains(brand)).toBe(false)
  })

  it('traduce roles y explica métricas sin cambiar identificadores', () => {
    expect(humanLabel('selection_oof')).toBe('Predicción de validación')
    expect(metricLabel('r2', 'R2')).toBe('R²')
    expect(metricExplanation('balanced_accuracy')).toMatch(/cada clase/)
  })

  it('escala importancias positivas, negativas y cero alrededor del centro', () => {
    expect(driverBar(2, 4)).toEqual({ side: 'positive', width: 25 })
    expect(driverBar(-4, 4)).toEqual({ side: 'negative', width: 50 })
    expect(driverBar(0, 4)).toEqual({ side: 'positive', width: 0 })
  })
})
