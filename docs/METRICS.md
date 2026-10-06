# Métricas

- MAE: promedio de `abs(actual - predicción)`, en unidad del target.
- RMSE: raíz del promedio del error cuadrático; penaliza errores grandes.
- R²: proporción relativa de variación; puede ser negativa y no es porcentaje de acierto. Es `null` con target constante o menos de dos casos.
- Balanced accuracy: promedio del recall de las clases; evita que una mayoría domine la lectura.
- Macro F1: F1 por clase con el mismo peso para cada una.
- WAPE: `sum(abs(error)) / sum(abs(actual))`; es `null` con denominador cero.

Toda métrica incluye población, rol de evaluación, unidad y motivo cuando no existe. No se fabrica incertidumbre a partir de residuos fitted ni se convierte error en “accuracy”.

