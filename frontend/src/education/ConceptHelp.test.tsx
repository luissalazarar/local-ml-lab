import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ConceptHelp } from './ConceptHelp'

describe('ConceptHelp', () => {
  it('abre ayuda educativa con teclado y Escape devuelve el foco', () => {
    render(<ConceptHelp concept="macro_f1" label="Entender F1 macro" />)
    const button = screen.getByRole('button', {name:'Entender F1 macro'})
    button.focus()
    fireEvent.click(button)
    expect(screen.getByRole('region', {name:/Ayuda sobre F1 macro/})).toBeTruthy()
    expect(screen.getByText(/Compáralo con la referencia/)).toBeTruthy()
    expect(button.getAttribute('aria-expanded')).toBe('true')
    fireEvent.keyDown(document, {key:'Escape'})
    expect(screen.queryByRole('region')).toBeNull()
    expect(document.activeElement).toBe(button)
  })
})
