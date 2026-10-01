# Motor ML v0.6

Cada run congela un `AnalysisPlan` antes de ajustar modelos. El plan registra versión de aplicación y políticas, versión preparada, objetivo, población y exclusiones, universo de clases, splits con membresía por `row_id` o periodo, candidatos con parámetros exactos, métrica, presupuestos y seed raíz. `plan_sha256` se calcula sobre el contenido analítico estable; una configuración distinta requiere otro run. Las seeds derivadas usan SHA-256 de seed, candidato y unidad, nunca `hash()` ni el UUID del run.

## Catálogo tabular

Regresión rápida compara la referencia mediana para MAE o media para RMSE/R² y Ridge. Recomendada añade Extra Trees y Random Forest. Clasificación rápida compara `DummyClassifier(prior)`, logística normal y logística con pesos balanceados. Recomendada añade Extra Trees, Random Forest normal y Random Forest balanceado. Los pesos cambian el coste de errores durante el entrenamiento; no crean observaciones.

Los árboles usan 100 estimadores, profundidad máxima 12, hoja mínima 2 y como máximo dos threads. Solo son elegibles cuando cada train tiene al menos 20 filas. Cada candidato y fold recibe un pipeline nuevo. Imputación, categorías raras, encoding, escalado lineal y descarte de constantes se aprenden solo en train. El resultado limita la expansión a 5000 features y rechaza matrices densas superiores a 64 MiB; no hace sampling silencioso.

Una selección explícita sin variables ejecuta solo la referencia. Omitir `included_column_ids` utiliza defaults elegibles; enviar `[]` conserva la selección vacía.

## Forecasting mensual

El catálogo rápido contiene último valor, media histórica, estacional ingenuo, tendencia lineal y Ridge con tendencia/mes. Recomendado añade Holt amortiguado y Holt-Winters aditivo amortiguado mediante `statsmodels==0.14.5`. Todos exponen una sola operación causal `fit_predict(prefix_values, prefix_dates, future_dates, frozen_config)`; backtest, prueba reservada y futuro usan esa misma implementación.

La elegibilidad usa el prefijo más corto del plan: 2 meses para último valor/media, 24 para estacional, 12 para tendencia lineal y Holt, 24 para Ridge con mes y 36 para Holt-Winters. Los modelos de Holt acotan damping entre 0.80 y 0.98, no usan búsqueda brute ni corrección de bias, y una no convergencia o salida no finita invalida el candidato sin bloquear los demás.

## Selección

`selection-policy-2.0` conserva por separado `best_observed`, referencia y modelo seleccionado. Para errores, empate práctico es 1 % del error de referencia y mejora mínima 3 %. Para accuracy/balanced accuracy/F1 macro son 0.005 y 0.02; para R², 0.01 y 0.02. Son políticas del producto, no pruebas de significancia.

Un candidato aprendido debe completar todas las unidades, mejorar conjuntamente, tener al menos tres comparaciones definibles, ganar al menos 60 %, lograr mediana positiva y no tener bloqueo metodológico. Si nadie pasa, gana la referencia. Entre candidatos que pasan y quedan dentro de la banda práctica, se prefiere menor complejidad, después score e ID. Una prueba reservada nunca cambia la selección ya congelada.

Las métricas conjuntas se recalculan desde todas las predicciones fuera de muestra alineadas por ID; no se promedian RMSE o F1 de folds. Se guardan métricas por unidad, media, mediana, desviación muestral y rango. Una sola unidad tiene desviación `null`. NaN/Infinity nunca se serializan.

Permutation importance se calcula después de seleccionar, como máximo en tres folds y tres repeticiones por fold, con presupuesto propio de 60 s. No participa en la selección y no demuestra causalidad. Una referencia sin features no recibe importancias inventadas.

## Ejecución y estado en vivo

El orden es referencia, candidatos aprendidos, selección, prueba reservada, futuro, explicación y snapshot. Los fits tienen presupuesto de 20 s en Rápido o 60 s en Recomendado; la selección dispone de 120/360 s. El proceso supervisor mantiene heartbeat, cancelación y terminación de descendientes. Un timeout deja el candidato incompleto y fuera del ranking.

El motor emite eventos estructurados por candidato y unidad. SQLite conserva la proyección `LiveRunState`; `RunResult` sigue siendo un snapshot inmutable. La cola transporta solo IDs y los procesos hijos nunca heredan conexiones SQLite.
