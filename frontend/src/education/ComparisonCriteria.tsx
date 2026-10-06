import { metricLabel } from '../presentation/labels'
import { betterMeans, consistencyRule, improvementRule, referenceRule, tieRule } from './comparisonRules'

type ComparisonCriteriaProps = {
  metricId: string | null | undefined
  problemType?: string | null
}

export function ComparisonCriteria({ metricId, problemType }: ComparisonCriteriaProps) {
  return <section className="panel metricInterpreter" aria-labelledby="comparison-criteria">
    <div className="panelTitle">
      <div>
        <span className="sectionQuestion">¿Qué es la referencia y cuándo un modelo es mejor?</span>
        <h2 id="comparison-criteria">Cómo decidimos que un modelo es mejor</h2>
      </div>
    </div>
    <div className="metricInterpretationGrid">
      <article>
        <strong>La referencia simple</strong>
        <p>Es una regla que no aprende nada y sirve de vara de medir: {referenceRule(problemType, metricId)}. Si un modelo no la supera con claridad, no aporta.</p>
      </article>
      <article>
        <strong>«Mejor» se mide con {metricLabel(metricId)}</strong>
        <p>Un modelo es mejor cuando {betterMeans(metricId)} que la referencia, con la misma métrica y las mismas pruebas, y solo en datos que no usó para aprender.</p>
      </article>
      <article>
        <strong>Tres condiciones para reemplazarla</strong>
        <ol className="metricChecklist">
          <li><strong>Mejora suficiente:</strong> {improvementRule(metricId)}.</li>
          <li><strong>Mejora consistente:</strong> {consistencyRule}.</li>
          <li><strong>Simplicidad:</strong> si dos modelos quedan prácticamente empatados ({tieRule(metricId)}), gana el más sencillo.</li>
        </ol>
        <small>Si ninguno cumple las tres, se conserva la referencia. Son reglas conservadoras del producto, no una prueba de significancia estadística.</small>
      </article>
    </div>
  </section>
}
