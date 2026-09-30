# Validación v0.6

## Tabular

El alcance exige registros independientes. Dependencia temporal o entidades repetidas necesitan otra estrategia y permanecen fuera de alcance. Las filas exactamente duplicadas se conservan, se agrupan por todo su contenido preparado —incluido target— y nunca cruzan train/validación.

Con N filas etiquetadas:

- regresión N=2..3: leave-one-out solo para referencias; N=4..9: K=min(3,floor(N/2)); N>=10: cinco folds;
- clasificación: K=min(5, soporte de la clase menos frecuente), con `StratifiedGroupKFold`; K solo baja si el soporte lo exige;
- cero/una fila, una clase o clase singleton: no evaluable.

Cuando N>=200 se intenta una sola reserva de 20 %. Regresión exige al menos 40 casos de test y 100 de desarrollo. Clasificación exige 25 casos por clase antes, 5 por clase en test y 10 en desarrollo. Si falla, toda la evidencia es selección y el resultado lo declara. La CV se construye únicamente dentro de desarrollo. Ganador y referencia se ajustan en desarrollo y se evalúan una sola vez en test; perder allí no cambia la selección.

## Forecasting

Se acepta una única serie mensual regular, sin meses inventados ni huecos comprimidos. Para N meses y horizonte H entre 1 y 24:

- W=36 si N>=36+3H; en otro caso W=24 si N>=24+3H; luego W=12 si N>=12+3H; de lo contrario W=2;
- se reservan los últimos H meses solo si N>=W+4H;
- D=N-H con test, o N sin test;
- K=min(3,floor((D-W)/H)) en Rápido y min(6,...) en Recomendado;
- origen j = D-KH+jH, con train `[0,origen)` y validación `[origen,origen+H)`.

Los bloques objetivo no se solapan y el entrenamiento es expansivo. Una emisión de H pasos es una unidad; los trains de orígenes distintos sí se solapan y no se presentan como muestras independientes. K=1 o K=2 permite comparación exploratoria, pero bloquea la recomendación de una mejora aprendida por consistencia insuficiente.

Con test, la selección usa solo `[0,D)`, después se evalúa `[D,N)` una vez y finalmente se reajusta la misma receta con `[0,N)` para el futuro real. El futuro contiene exactamente H meses con `actual=null` y `error=null`.

## Evidencia y límites

El producto separa estado técnico, selección y evidencia. Un candidato incompleto nunca gana. Métricas indefinidas son `null` con motivo. Matrices de clasificación conservan el universo completo; precisión sin predicciones es `null`, mientras F1=0 es válido cuando su denominador de conteos sí existe.

La prueba reservada repetidamente consultada no equivale a datos externos nuevos. Una referencia ganadora significa “no encontramos una mejora suficiente entre los candidatos probados”, no “no existe señal”. Confiabilidad describe cobertura y modo de evaluación; nunca es probabilidad.
