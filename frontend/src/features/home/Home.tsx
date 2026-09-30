import { Link, useNavigate } from 'react-router-dom'
import { BrandSymbol } from '../../brand/BrandSymbol'

const capabilities = [
  ['Estimar un valor', 'Duración, cantidad, consumo o costo.'],
  ['Predecir una categoría', 'Sí/no o varias categorías.'],
  ['Estimar próximos meses', 'Una serie mensual, sin meses faltantes.'],
  ['Entender variables útiles', 'Importancia predictiva, no causalidad.'],
  ['Explorar la data', 'Calidad, tipos y problemas sin entrenar.'],
]

export function Home() {
  const navigate = useNavigate()
  return (
    <main>
      <section className="hero">
        <div>
          <span className="eyebrow">Procesamiento local · Sin GPU obligatoria</span>
          <h1>Tu data puede contar una historia.<br /><em>Primero hay que comprobarla.</em></h1>
          <p>
            Sube tu archivo, elige qué quieres estimar o entender y revisaremos la calidad.
            Esta beta exploratoria compara referencias y modelos y explica sus límites sin prometer certeza.
          </p>
          <div className="actions">
            <Link className="button primary" to="/new">Analizar mi archivo</Link>
            <button className="button secondary" onClick={() => navigate('/new?example=regression')}>
              Probar con datos de ejemplo
            </button>
          </div>
        </div>
        <aside className="trustCard">
          <BrandSymbol className="trustSymbol" tone="inverse" size={48} />
          <strong>Tus datos se procesan en este equipo</strong>
          <p>
            No necesitas una API key. Puedes revisar y copiar un contexto seguro para usarlo
            explícitamente con la IA que elijas.
          </p>
          <dl>
            <div><dt>5</dt><dd>formas de analizar</dd></div>
            <div><dt>3</dt><dd>formatos de archivo</dd></div>
          </dl>
        </aside>
      </section>
      <section className="capabilities" aria-labelledby="cap">
        <div className="sectionIntro">
          <span>QUÉ PUEDES HACER</span>
          <h2 id="cap">Empieza por tu pregunta, no por un algoritmo.</h2>
        </div>
        <div className="cardGrid">
          {capabilities.map(([title, description]) => (
            <article className="capCard" key={title}>
              <h3>{title}</h3><p>{description}</p>
            </article>
          ))}
        </div>
      </section>
      <section className="baselineNote">
        <div>
          <span className="dot">i</span>
          <div>
            <strong>Una referencia sencilla también puede ganar.</strong>
            <p>Es una comparación necesaria: permite saber si un modelo aporta algo adicional.</p>
          </div>
        </div>
        <Link to="/new">Comenzar análisis</Link>
      </section>
    </main>
  )
}
