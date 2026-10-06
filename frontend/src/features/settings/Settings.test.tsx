import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Settings } from './Settings'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

describe('borrado seguro de datos locales', () => {
  it('requiere confirmación y usa el endpoint único de limpieza', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/system')) return { ok: true, json: async () => ({ display_version: '0.7.0001', version: '0.7.1', api: 'ready', queue: 'ready', worker: 'ready', limits: {}, capabilities: {} }) }
      if (url.endsWith('/datasets')) return { ok: true, json: async () => ({ items: [] }) }
      if (url.endsWith('/local-data') && init?.method === 'DELETE') return { ok: true, json: async () => ({ status: 'deleted' }) }
      throw new Error(`Unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    vi.spyOn(window, 'confirm').mockReturnValue(true)

    render(<MemoryRouter><Settings /></MemoryRouter>)
    const button = await screen.findByRole('button', { name: 'Borrar datos guardados' })
    fireEvent.click(button)

    await waitFor(() => expect(screen.getByRole('status').textContent).toMatch(/Se borraron los datos/))
    expect(window.confirm).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/local-data', expect.objectContaining({ method: 'DELETE', credentials: 'same-origin' }))
  })
})
