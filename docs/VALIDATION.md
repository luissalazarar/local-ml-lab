# Validación

La validación se decide antes del modelo y se registra por `row_id`. Regresión IID usa hasta cinco folds; clasificación usa folds estratificados limitados por la clase más rara. Una clase singleton o un solo registro hacen que el alcance predictivo no sea evaluable.

Forecasting V1 acepta una serie mensual regular. Ordena y agrega por mes cuando el usuario elige explícitamente suma o media, rechaza huecos y emite predicciones causales: el futuro nunca entra en lags del prefijo. El holdout mensual sirve para seleccionar el candidato y queda etiquetado como `selection_monthly_holdout`; no se presenta como test final. Las filas futuras se distinguen como `forecast_future`. Esta versión no muestra bandas porque no dispone de calibración independiente suficiente.

La implementación actual expone `selection_cv`, `selection_monthly_holdout` y `not_evaluable`. Nested CV, calibración formal y conformal quedan en el roadmap. Una validación usada para seleccionar configura evidencia exploratoria y limita la confiabilidad a BAJA. Regresión y clasificación asumen registros independientes; datos por persona, grupo o tiempo requieren una estrategia distinta y no deben interpretarse como cubiertos por esta V1.
