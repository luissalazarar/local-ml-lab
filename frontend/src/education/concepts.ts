export type Concept = {
  name: string
  short: string
  extended?: string
  interpretation?: string
  direction?: 'higher' | 'lower' | 'none'
  range?: string
  compareAgainst?: string
  goodBad?: string
  warning?: string
}

export const concepts: Record<string, Concept> = {
  regression: { name: 'Regresión', short: 'Estima un valor numérico.', extended: 'Se usa cuando el resultado es una cantidad, costo, duración o medida.' },
  classification: { name: 'Clasificación', short: 'Predice una categoría.', extended: 'Necesita al menos dos clases y suficientes ejemplos reales de cada una.' },
  forecasting: { name: 'Pronóstico', short: 'Estima meses futuros de una serie.', extended: 'V1 requiere una fecha mensual, un resultado numérico y calendario continuo.' },
  exploration: { name: 'Exploración', short: 'Revisa estructura y calidad sin entrenar.' },
  drivers: { name: 'Importancia de variables', short: 'Mide cuánto ayudó una variable a predecir.', warning: 'Importancia predictiva no significa causalidad.' },
  observation: { name: 'Observación', short: 'Una fila que representa un caso, evento o periodo.' },
  variable: { name: 'Variable', short: 'Una columna que describe una característica.' },
  feature: { name: 'Variable disponible para el modelo', short: 'Una columna que sí puede existir cuando hagas la predicción.', extended: 'En machine learning también suele llamarse feature.' },
  target: { name: 'Resultado que quieres predecir', short: 'La columna que el modelo intentará estimar o clasificar.', extended: 'En machine learning suele llamarse target. Se elige para un análisis concreto, después de preparar la tabla.' },
  original: { name: 'Original', short: 'Tu archivo tal como lo subiste; nunca se modifica durante la preparación.' },
  prepared_version: { name: 'Versión preparada', short: 'Una copia con tipos y representaciones que tú confirmaste.', extended: 'Todavía no contiene un modelo ni decisiones que dependen del resultado a predecir.' },
  recipe: { name: 'Receta', short: 'Un archivo pequeño que guarda decisiones de preparación, no tus datos.', extended: 'Permite repetir reglas en otro archivo compatible. No contiene modelos ni ejecuta código.' },
  quarantined_row: { name: 'Fila apartada', short: 'Una fila que no participa en esa versión o análisis, pero sigue existiendo en el original.' },
  detected_type: { name: 'Tipo detectado', short: 'La interpretación inicial de una columna basada en su contenido.', warning: 'Es una sugerencia, no una certeza.' },
  column_role: { name: 'Uso de columna', short: 'Indica si una columna podrá ayudar al modelo, identifica registros o debe ignorarse.' },
  decimal_separator: { name: 'Separador decimal', short: 'El signo que separa la parte entera de los decimales, como la coma en 1.234,50.' },
  thousands_separator: { name: 'Separador de miles', short: 'El signo que agrupa miles, como el punto en 1.234,50.' },
  aggregation: { name: 'Agregación', short: 'Resume varias observaciones en un único valor por periodo.' },
  monthly_sum: { name: 'Suma mensual', short: 'Suma cantidades acumulables, como ventas totales de un mes.' },
  monthly_mean: { name: 'Promedio mensual', short: 'Resume el nivel medio de una medida, como temperatura mensual.' },
  filter: { name: 'Filtro', short: 'Aparta filas según una condición explícita que tú confirmas.' },
  category_mapping: { name: 'Unificación de categorías', short: 'Convierte un valor escrito de una forma a otra que tú confirmas, por ejemplo NORTE a Norte.', warning: 'No combina tablas ni busca coincidencias aproximadas.' },
  prepared_data: { name: 'Preparado', short: 'Datos que quedaron en la versión preparada después de aplicar tus decisiones.' },
  used_data: { name: 'Datos usados', short: 'Filas que sí pudieron participar en un análisis concreto.' },
  numeric: { name: 'Numérica', short: 'Valores que representan cantidades.' },
  categorical: { name: 'Categórica', short: 'Etiquetas o grupos.' },
  datetime: { name: 'Fecha', short: 'Valores interpretados como fechas.' },
  identifier: { name: 'Posible identificador', short: 'Parece identificar registros individuales y normalmente no ayuda a generalizar; se excluye por defecto.' },
  missing: { name: 'Faltante', short: 'Una fila sin valor para esta variable.' },
  duplicate: { name: 'Duplicado', short: 'Una fila idéntica a otra; conviene confirmar si es un caso real repetido.' },
  training: { name: 'Entrenamiento', short: 'Parte de los datos usada para aprender el patrón.' },
  validation: { name: 'Validación', short: 'Datos apartados para comprobar el ajuste.', warning: 'Aquí también participa en la selección; no es una prueba final independiente.' },
  fold: { name: 'Partición de validación', short: 'Una separación concreta de datos para entrenar y comprobar sin mezclar ambos usos.' },
  cross_validation: { name: 'Validación cruzada', short: 'Repite entrenamiento y validación con distintas particiones.' },
  split: { name: 'Partición', short: 'Una separación concreta entre entrenamiento y validación.' },
  baseline: { name: 'Baseline o referencia', short: 'Una regla que no aprende, usada como vara de medir: predice siempre la mediana o el promedio, la clase más frecuente o el último valor.', extended: 'Un modelo es mejor solo si, con la misma métrica y en datos que no vio al entrenar, supera a la referencia por un margen suficiente y de forma consistente.' },
  model: { name: 'Modelo', short: 'Una regla aprendida a partir de los datos de entrenamiento.' },
  candidate: { name: 'Candidato', short: 'Una forma de predecir que compite bajo el mismo plan de evaluación.' },
  selection: { name: 'Selección', short: 'La comparación que decide qué candidato cumple mejor las reglas sin mirar la prueba reservada.' },
  confirmation: { name: 'Confirmación', short: 'Una segunda comparación reproducible entre el provisional y la referencia.', warning: 'Usa datos de desarrollo, nunca la prueba reservada.' },
  holdout: { name: 'Prueba reservada', short: 'Datos que no participan en elegir el modelo y se revisan después.', warning: 'Su resultado no cambia el ganador.' },
  backtest: { name: 'Prueba histórica', short: 'Simula una predicción hecha en una fecha pasada usando solo lo conocido hasta entonces.' },
  origin: { name: 'Origen de pronóstico', short: 'La última fecha que el método conoce antes de estimar los meses siguientes.' },
  leakage: { name: 'Leakage', short: 'Información que revela el resultado antes de tiempo.', warning: 'La app ayuda a evitar fugas técnicas, pero no conoce todas las reglas de tu negocio.' },
  imputation: { name: 'Imputación', short: 'Completa faltantes con una regla aprendida solo en entrenamiento.' },
  encoding: { name: 'Encoding', short: 'Convierte categorías a una representación que el modelo puede usar.' },
  scaling: { name: 'Escalado', short: 'Ajusta la escala de números cuando el modelo lo necesita.' },
  class_weight: { name: 'Pesos de clase', short: 'Hace que ciertos errores cuesten más durante el entrenamiento.', warning: 'No crea filas ni ejemplos nuevos.' },
  mae: { name: 'MAE', short: 'Error absoluto promedio. Está en la misma unidad del resultado.', direction: 'lower', interpretation: 'Más bajo es mejor.', compareAgainst: 'Compáralo con el MAE de la referencia y con el error que sería tolerable en tu decisión real.', goodBad: 'No existe un MAE universalmente bueno: 10 puede ser pequeño para ventas mensuales y enorme para una medida entre 0 y 20.' },
  rmse: { name: 'RMSE', short: 'Mide error en la unidad del resultado y castiga más los errores grandes.', direction: 'lower', interpretation: 'Más bajo es mejor.', compareAgainst: 'Compáralo con el RMSE de la referencia y con MAE: si RMSE es mucho mayor, algunos errores grandes están pesando bastante.', goodBad: 'Es útil si los errores grandes cuestan más, pero no tiene un umbral universal de bueno o malo.' },
  r2: { name: 'R²', short: 'Compara el ajuste frente a predecir siempre el promedio.', direction: 'higher', range: 'Puede ser negativo; 0 equivale a la referencia del promedio y 1 es ajuste perfecto en esos datos.', compareAgainst: 'Su cero ya tiene una referencia concreta: predecir siempre el promedio. También conviene compararlo con el mismo modelo en otras particiones.', goodBad: 'Un valor positivo supera al promedio en esa evaluación; uno negativo rinde peor. Aun así, la utilidad depende del error en unidades reales y de su estabilidad.', warning: 'No es un porcentaje de acierto.' },
  accuracy: { name: 'Exactitud', short: 'Proporción total de predicciones correctas.', direction: 'higher', range: 'De 0 a 1; por ejemplo, 0,80 significa 80 aciertos por cada 100 casos evaluados.', compareAgainst: 'Compárala con la clase frecuente y revisa además qué ocurrió en cada categoría.', goodBad: 'No hay un corte universal: el costo de cada error y el balance entre clases definen si sirve.', warning: 'Puede engañar si una clase domina.' },
  balanced_accuracy: { name: 'Exactitud balanceada', short: 'Calcula el acierto de cada clase y después los promedia.', direction: 'higher', range: 'De 0 a 1.', interpretation: 'Más alto es mejor y cada clase pesa lo mismo.', compareAgainst: 'Compárala con la referencia y revisa el recall de cada clase para detectar categorías ignoradas.', goodBad: 'Un valor alto puede ocultar una clase problemática; la matriz de confusión completa la lectura.' },
  macro_f1: { name: 'F1 macro', short: 'Combina precisión y cobertura para cada categoría y da el mismo peso a todas.', extended: 'Si hay 90 casos A y 10 casos B, primero calcula F1 por separado para A y B. Luego promedia ambos resultados sin dejar que A domine solo por ser más frecuente.', direction: 'higher', range: 'Más alto es mejor · rango de 0 a 1.', interpretation: 'Ayuda a comprobar que el modelo no funcione bien solo para la clase mayoritaria.', compareAgainst: 'Compáralo con la referencia y revisa precisión, recall y soporte por categoría.', goodBad: 'No hay un umbral universal: importa qué errores puedes aceptar y si todas las clases relevantes tienen soporte suficiente.' },
  precision: { name: 'Precisión', short: 'De los casos predichos como una clase, cuántos eran realmente de esa clase.' },
  recall: { name: 'Recall o cobertura', short: 'De los casos reales de una clase, cuántos fueron encontrados.' },
  support: { name: 'Soporte', short: 'Cantidad de casos reales disponibles para una clase.' },
  confusion_matrix: { name: 'Matriz de confusión', short: 'Cruza categoría real por fila y predicha por columna; la diagonal son aciertos.' },
  prediction: { name: 'Predicción', short: 'Resultado estimado por un modelo para una observación.' },
  error: { name: 'Error', short: 'En regresión: predicho menos real.' },
  reliability: { name: 'Confiabilidad', short: 'Resume qué tan sólida fue la evaluación.', warning: 'No es una probabilidad de acierto.' },
  horizon: { name: 'Horizonte', short: 'Cantidad de meses futuros que se estimarán.' },
  trend: { name: 'Tendencia', short: 'Movimiento general de una serie a lo largo del tiempo.' },
  seasonality: { name: 'Estacionalidad', short: 'Un patrón que se repite en periodos equivalentes.' },
  dummy_median: { name: 'Mediana', short: 'Predice siempre un valor central. Es una referencia mínima.' },
  dummy_mean: { name: 'Media', short: 'Predice siempre el promedio de entrenamiento. Es la referencia para RMSE o R².' },
  dummy_prior: { name: 'Clase frecuente', short: 'Predice la categoría más común.' },
  ridge: { name: 'Ridge', short: 'Modelo lineal con regularización que limita coeficientes extremos.' },
  logistic_regression: { name: 'Logística', short: 'Modelo lineal para categorías.' },
  logistic_regression_balanced: { name: 'Logística con pesos balanceados', short: 'Da más peso a los errores de clases con menos casos; no crea observaciones.' },
  extra_trees: { name: 'Extra Trees', short: 'Combina muchos árboles aleatorizados y puede capturar relaciones no lineales.' },
  random_forest: { name: 'Random Forest', short: 'Combina muchos árboles construidos con distintas muestras.' },
  last_value: { name: 'Último valor', short: 'Usa el último dato conocido como referencia.' },
  historical_mean: { name: 'Media histórica', short: 'Usa la media del prefijo conocido como referencia para series dominadas por ruido.' },
  seasonal_naive: { name: 'Estacional', short: 'Usa el valor equivalente de una temporada anterior.' },
  linear_trend: { name: 'Tendencia lineal', short: 'Prolonga una tendencia recta aprendida solo con el histórico disponible.' },
  ridge_trend_month: { name: 'Ridge con tendencia y mes', short: 'Combina tiempo y mes del calendario; incluir ese componente no demuestra estacionalidad.' },
  holt_damped: { name: 'Holt amortiguado', short: 'Continúa una tendencia, reduciendo gradualmente su fuerza hacia adelante.' },
  holt_winters_add_damped: { name: 'Holt-Winters aditivo amortiguado', short: 'Combina nivel, tendencia y diferencias que se repiten entre meses.' },
  permutation_importance: { name: 'Importancia por permutación', short: 'Mide cuánto cambia el rendimiento al alterar una variable en datos de validación.', warning: 'No demuestra causalidad.' },
  p90_error: { name: 'P90 del error absoluto', short: 'El 90% de los errores absolutos fue igual o menor que este valor.', compareAgainst: 'Compáralo con el máximo error que tu uso real puede tolerar y con la mediana del error absoluto.', goodBad: 'Cuanto más se aleja de la mediana, más importante es revisar los casos con errores grandes.', warning: 'Describe errores grandes; no participa en la selección.' },
}

export function explain(id: string) {
  const item = concepts[id]
  if (!item) return ''
  return [item.short, item.interpretation, item.warning].filter(Boolean).join(' ')
}

export const excelChecklist = [
  'Una fila = una observación y una columna = una variable.',
  'Usa una fila de encabezados clara y una tabla principal por hoja.',
  'Evita celdas combinadas, títulos decorativos y subtotales dentro de la tabla.',
  'Mantén la misma unidad dentro de una columna y nombres de categorías consistentes.',
  'Los faltantes pueden quedar vacíos; evita columnas con dos ideas distintas.',
  'Puedes conservar IDs: la app intentará detectarlos y excluirlos del modelo.',
  'No incluyas información que solo conocerías después del resultado que quieres predecir.',
]

export const preparationReality = {
  yes: ['Conserva el original.', 'Detecta algunos problemas y posibles IDs.', 'Imputa faltantes dentro del entrenamiento.', 'Codifica categorías y escala números cuando corresponde.'],
  no: ['No corrige automáticamente todos los errores ni elimina outliers.', 'No entiende tu negocio ni arregla categorías mal escritas.', 'No evita todo leakage ni convierte mala data en buena data.'],
}
