export function DataFlow({ compact = false }: { compact?: boolean }) {
  const items = [
    ['ORIGINAL', 'Tu archivo tal como lo subiste.'],
    ['PREPARADO', 'Tipos y representaciones que tú confirmaste. El original no cambia.'],
    ['ANÁLISIS', 'Objetivo, filas disponibles y decisiones que dependen de lo que quieres predecir.'],
    ['ENTRENAMIENTO', 'El modelo aprende imputación, categorías y escalas usando solo su parte de entrenamiento.'],
  ]
  return <ol className={`dataFlow ${compact ? 'compactFlow' : ''}`} aria-label="Flujo de los datos">
    {items.map(([title, description]) => <li key={title}><strong>{title}</strong><span>{description}</span></li>)}
  </ol>
}
