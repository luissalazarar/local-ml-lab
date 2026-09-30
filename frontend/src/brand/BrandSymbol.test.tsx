import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import favicon from '../../public/favicon.svg?raw'
import inverse from '../../public/brand/laboratorio-ml-simbolo-inverso.svg?raw'
import mono from '../../public/brand/laboratorio-ml-simbolo-mono.svg?raw'
import reduced from '../../public/brand/laboratorio-ml-simbolo-reducido.svg?raw'
import main from '../../public/brand/laboratorio-ml-simbolo.svg?raw'
import { BrandSymbol } from './BrandSymbol'
import { symbolGeometry } from './symbolGeometry'

describe('símbolo de marca', () => {
  it('mantiene los SVG publicados sincronizados con el componente', () => {
    for (const file of [main, mono, inverse]) {
      expect(file).toContain(`d="${symbolGeometry.full.sheet}"`)
      expect(file).toContain(`d="${symbolGeometry.full.heldOut}"`)
    }
    for (const file of [reduced, favicon]) {
      expect(file).toContain(`d="${symbolGeometry.reduced.sheet}"`)
      expect(file).toContain(`d="${symbolGeometry.reduced.heldOut}"`)
    }
  })

  it('publica SVG sin scripts, raster, fuentes ni recursos externos', () => {
    for (const file of [main, mono, inverse, reduced, favicon]) {
      expect(file).not.toMatch(/<script|<image|<foreignObject|@font-face|@import|href=|url\(/i)
    }
  })

  it('usa la versión reducida en tamaños pequeños', () => {
    const { container, rerender } = render(<BrandSymbol size={16} />)
    expect(container.querySelector('path')?.getAttribute('d')).toBe(symbolGeometry.reduced.sheet)
    rerender(<BrandSymbol size={40} />)
    expect(container.querySelector('path')?.getAttribute('d')).toBe(symbolGeometry.full.sheet)
  })

  it('es decorativo junto al nombre y nombrable cuando aparece solo', () => {
    const { container, rerender } = render(<BrandSymbol />)
    const svg = () => container.querySelector('svg')!
    expect(svg().getAttribute('aria-hidden')).toBe('true')
    expect(svg().getAttribute('role')).toBeNull()
    rerender(<BrandSymbol label="Laboratorio ML" />)
    expect(svg().getAttribute('role')).toBe('img')
    expect(svg().getAttribute('aria-label')).toBe('Laboratorio ML')
    expect(svg().getAttribute('aria-hidden')).toBeNull()
  })
})
