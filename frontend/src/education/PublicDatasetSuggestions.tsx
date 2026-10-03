import type { ReactNode } from 'react'

const External = ({ href, children }: { href: string, children: ReactNode }) => (
  <a href={href} target="_blank" rel="noopener noreferrer">{children} ↗</a>
)

export function PublicDatasetSuggestions({ compact = false }: { compact?: boolean }) {
  if (compact) return <>
    <p>Son enlaces externos; la app no descarga ni envía datos automáticamente.</p>
    <nav className="publicDatasetLinks" aria-label="Datasets públicos sugeridos">
      <External href="https://archive.ics.uci.edu/dataset/360/air+quality">Air Quality</External>
      <External href="https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset">Bike Sharing</External>
      <External href="https://archive.ics.uci.edu/dataset/222/bank+marketing">Bank Marketing</External>
      <External href="https://www.datosabiertos.gob.pe/">Datos Abiertos del Perú</External>
    </nav>
  </>
  return <>
    <p>Son referencias externas; la aplicación no descarga ni envía datos a estos sitios.</p>
    <div className="datasetList">
      <article>
        <h3><External href="https://archive.ics.uci.edu/">UCI Machine Learning Repository</External></h3>
        <p>Datasets abiertos para practicar regresión y clasificación.</p>
        <ul>
          <li><External href="https://archive.ics.uci.edu/dataset/360/air+quality">Air Quality</External>: Excel para exploración y regresión.</li>
          <li><External href="https://archive.ics.uci.edu/dataset/275/bike+sharing+dataset">Bike Sharing</External>: demanda para regresión.</li>
          <li><External href="https://archive.ics.uci.edu/dataset/222/bank+marketing">Bank Marketing</External>: clasificación yes/no.</li>
        </ul>
      </article>
      <article>
        <h3><External href="https://www.datosabiertos.gob.pe/">Datos Abiertos del Perú</External></h3>
        <p>Muchos CSV y XLSX requieren elegir hoja y reorganizar subtotales o cabeceras.</p>
      </article>
    </div>
  </>
}
