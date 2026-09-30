# Validación

La validación se decide antes del modelo y se registra por `row_id`. Regresión IID usa hasta cinco folds; clasificación usa folds estratificados limitados por la clase más rara. Una clase singleton o un solo registro hacen que el alcance predictivo no sea evaluable.

Forecasting ordena por fecha y emite predicciones causales: el futuro nunca entra en lags del prefijo. Un holdout de `H` periodos representa una emisión, no `H` orígenes independientes. Las bandas solo pueden mostrarse tras calibración separada con 20 errores válidos por horizonte; de lo contrario son `null` con motivo.

La implementación actual expone `selection_cv`, `selection_single_split` y `not_evaluable`. Nested CV, calibración formal y conformal quedan en el roadmap. Una validación usada para seleccionar configura evidencia exploratoria y limita la confiabilidad a BAJA.

