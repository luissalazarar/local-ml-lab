import { REDUCED_MAX_SIZE, symbolGeometry } from './symbolGeometry'

type Tone = 'color' | 'mono' | 'inverse'

const tones: Record<Tone, { sheet: string; heldOut: string }> = {
  color: { sheet: 'var(--brand-petroleum, #054D61)', heldOut: 'var(--brand-turquoise, #049990)' },
  mono: { sheet: 'currentColor', heldOut: 'currentColor' },
  inverse: { sheet: '#FFFFFF', heldOut: '#FFFFFF' },
}

type Props = {
  size?: number
  tone?: Tone
  className?: string
  /** Solo cuando el símbolo aparece sin el nombre visible; si acompaña al texto queda oculto al lector de pantalla. */
  label?: string
}

export function BrandSymbol({ size = 40, tone = 'color', className, label }: Props) {
  const shape = size <= REDUCED_MAX_SIZE ? symbolGeometry.reduced : symbolGeometry.full
  const fill = tones[tone]
  const a11y = label ? { role: 'img', 'aria-label': label } : { 'aria-hidden': true as const }
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 48 48" focusable="false" {...a11y}>
      <path fill={fill.sheet} fillRule="evenodd" d={shape.sheet} />
      <path fill={fill.heldOut} fillRule="evenodd" d={shape.heldOut} />
    </svg>
  )
}
