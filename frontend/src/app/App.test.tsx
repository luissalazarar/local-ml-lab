import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Home } from '../features/home/Home'

describe('contrato básico', () => {
  it('presenta la acción principal sin jerga técnica', () => {
    render(<MemoryRouter><Home /></MemoryRouter>)
    expect(screen.getByRole('link', {name: 'Analizar mi archivo'})).toBeTruthy()
    expect(screen.getByText(/Tus datos se procesan en este equipo/)).toBeTruthy()
  })
})
