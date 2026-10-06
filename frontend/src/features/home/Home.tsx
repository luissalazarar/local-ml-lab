import { Link, useNavigate } from 'react-router-dom'
import { BrandSymbol } from '../../brand/BrandSymbol'
import { PublicDatasetSuggestions } from '../../education/PublicDatasetSuggestions'

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
            Sube tu Excel o archivo de datos, elige qué quieres estimar o entender y revisaremos la calidad.
            Esta beta exploratoria compara referencias y modelos y explica sus límites sin prometer certeza.
          </p>
          <div className="actions">
            <Link className="button primary" to="/new">Analizar mi archivo</Link>
            <button className="button secondary" onClick={() => navigate('/new?examples=1')}>
              Probar con datos de ejemplo
            </button>
          </div>
          <div className="heroDatasets" aria-labelledby="home-datasets-title">
            <strong id="home-datasets-title">Datasets públicos para probar</strong>
            <PublicDatasetSuggestions compact />
          </div>
        </div>
        <div className="trustCard">
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
        </div>
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
            <p>Representa qué se logra sin usar variables: mediana o promedio, clase frecuente o la mejor pauta histórica simple. Un modelo solo la reemplaza si supera esa misma regla en los mismos casos apartados, por un margen y con una consistencia definidos; la Guía muestra cada criterio.</p>
          </div>
        </div>
        <Link to="/new">Comenzar análisis</Link>
      </section>
    </main>
  )
}
