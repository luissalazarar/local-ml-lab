export type Concept = {
  name: string
  short: string
  extended?: string
  interpretation?: string
  direction?: 'higher' | 'lower' | 'none'
  range?: string
  warning?: string
}

export const concepts: Record<string, Concept> = {
  regression: { name: 'Regresión', short: 'Estima un valor numérico.', extended: 'Se usa cuando el resultado es una cantidad, costo, duración o medida.' },
  classification: { name: 'Clasificación', short: 'Predice una categoría.', extended: 'Necesita al menos dos clases y suficientes ejemplos reales de cada una.' },
  forecasting: { name: 'Pronóstico', short: 'Estima meses futuros de una serie.', extended: 'V1 requiere una fecha mensual, target numérico y calendario continuo.' },
  exploration: { name: 'Exploración', short: 'Revisa estructura y calidad sin entrenar.' },
  drivers: { name: 'Importancia de variables', short: 'Mide cuánto ayudó una variable a predecir.', warning: 'Importancia predictiva no significa causalidad.' },
  observation: { name: 'Observación', short: 'Una fila que representa un caso, evento o periodo.' },
  variable: { name: 'Variable', short: 'Una columna que describe una característica.' },
  target: { name: 'Target', short: 'La columna que quieres estimar o clasificar.' },
  numeric: { name: 'Numérica', short: 'Valores que representan cantidades.' },
  categorical: { name: 'Categórica', short: 'Etiquetas o grupos.' },
  datetime: { name: 'Fecha', short: 'Valores interpretados como fechas.' },
  identifier: { name: 'Posible identificador', short: 'Parece identificar registros individuales y normalmente no ayuda a generalizar; se excluye por defecto.' },
  missing: { name: 'Faltante', short: 'Una fila sin valor para esta variable.' },
  duplicate: { name: 'Duplicado', short: 'Una fila idéntica a otra; conviene confirmar si es un caso real repetido.' },
  training: { name: 'Entrenamiento', short: 'Parte de los datos usada para aprender el patrón.' },
  validation: { name: 'Validación', short: 'Datos apartados para comprobar el ajuste.', warning: 'Aquí también participa en la selección; no es una prueba final independiente.' },
  cross_validation: { name: 'Validación cruzada', short: 'Repite entrenamiento y validación con distintas particiones.' },
  split: { name: 'Partición', short: 'Una separación concreta entre entrenamiento y validación.' },
  baseline: { name: 'Baseline o referencia', short: 'Una regla sencilla que el modelo debería intentar superar.' },
  model: { name: 'Modelo', short: 'Una regla aprendida a partir de los datos de entrenamiento.' },
  leakage: { name: 'Leakage', short: 'Información que revela el resultado antes de tiempo.', warning: 'La app ayuda a evitar fugas técnicas, pero no conoce todas las reglas de tu negocio.' },
  imputation: { name: 'Imputación', short: 'Completa faltantes con una regla aprendida solo en entrenamiento.' },
  encoding: { name: 'Encoding', short: 'Convierte categorías a una representación que el modelo puede usar.' },
  scaling: { name: 'Escalado', short: 'Ajusta la escala de números cuando el modelo lo necesita.' },
  mae: { name: 'MAE', short: 'Error absoluto promedio. Está en la misma unidad del resultado.', direction: 'lower', interpretation: 'Más bajo es mejor.' },
  rmse: { name: 'RMSE', short: 'Mide error y penaliza más los errores grandes.', direction: 'lower', interpretation: 'Más bajo es mejor.' },
  r2: { name: 'R²', short: 'Compara el ajuste frente a una referencia basada en el promedio.', direction: 'higher', range: 'Puede ser negativo; 1 es ajuste perfecto en esos datos.', warning: 'No es un porcentaje de acierto.' },
  accuracy: { name: 'Exactitud', short: 'Proporción total de predicciones correctas.', direction: 'higher', range: 'De 0 a 1.', warning: 'Puede engañar si una clase domina.' },
  balanced_accuracy: { name: 'Exactitud balanceada', short: 'Calcula el acierto de cada clase y después los promedia.', direction: 'higher', range: 'De 0 a 1.', interpretation: 'Útil cuando las clases están desbalanceadas.' },
  macro_f1: { name: 'F1 macro', short: 'Calcula F1 para cada clase y les da el mismo peso.', direction: 'higher', range: 'De 0 a 1.', interpretation: 'Ayuda a comprobar que el modelo no funcione bien solo para la clase mayoritaria.' },
  precision: { name: 'Precisión', short: 'De los casos predichos como una clase, cuántos eran realmente de esa clase.' },
  recall: { name: 'Recall o cobertura', short: 'De los casos reales de una clase, cuántos fueron encontrados.' },
  support: { name: 'Soporte', short: 'Cantidad de casos reales disponibles para una clase.' },
  confusion_matrix: { name: 'Matriz de confusión', short: 'Cruza categoría real por fila y predicha por columna; la diagonal son aciertos.' },
  prediction: { name: 'Predicción', short: 'Resultado estimado por un modelo para una observación.' },
  error: { name: 'Error', short: 'En regresión: predicho menos real.' },
  reliability: { name: 'Confiabilidad', short: 'Resume qué tan sólida fue la evaluación.', warning: 'No es una probabilidad de acierto.' },
  horizon: { name: 'Horizonte', short: 'Cantidad de meses futuros que se estimarán.' },
  seasonality: { name: 'Estacionalidad', short: 'Un patrón que se repite en periodos equivalentes.' },
  dummy_median: { name: 'Mediana', short: 'Predice siempre un valor central. Es una referencia mínima.' },
  dummy_prior: { name: 'Clase frecuente', short: 'Predice la categoría más común.' },
  ridge: { name: 'Ridge', short: 'Modelo lineal con regularización que limita coeficientes extremos.' },
  logistic_regression: { name: 'Logística', short: 'Modelo lineal para categorías.' },
  extra_trees: { name: 'Extra Trees', short: 'Combina muchos árboles aleatorizados y puede capturar relaciones no lineales.' },
  random_forest: { name: 'Random Forest', short: 'Combina muchos árboles construidos con distintas muestras.' },
  last_value: { name: 'Último valor', short: 'Usa el último dato conocido como referencia.' },
  seasonal_naive: { name: 'Estacional', short: 'Usa el valor equivalente de una temporada anterior.' },
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
