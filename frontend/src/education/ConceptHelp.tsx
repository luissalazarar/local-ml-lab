import { useEffect, useId, useRef, useState } from 'react'
import { concepts } from './concepts'

export function ConceptHelp({ concept, label = '¿Qué significa?' }: { concept: string, label?: string }) {
  const item = concepts[concept]
  const [open, setOpen] = useState(false)
  const id = useId()
  const buttonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }
    document.addEventListener('keydown', close)
    return () => document.removeEventListener('keydown', close)
  }, [open])

  if (!item) return null
  return <div className="conceptHelp">
    <button ref={buttonRef} type="button" className="conceptHelpButton" aria-expanded={open} aria-controls={id} onClick={() => setOpen(value => !value)}>{label}</button>
    {open && <div id={id} className="conceptHelpBody" role="region" aria-label={`Ayuda sobre ${item.name}`}>
      <strong>{item.name}</strong>
      <p>{item.short}</p>
      {item.extended && <p>{item.extended}</p>}
      {[item.interpretation, item.range, item.compareAgainst, item.goodBad, item.warning].filter(Boolean).map(text => <small key={text}>{text}</small>)}
    </div>}
  </div>
}
