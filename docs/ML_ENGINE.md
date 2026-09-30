# Motor ML

El registry incluye referencias simples, Ridge/logística, Extra Trees y Random Forest para problemas tabulares, además de referencias causales para forecasting. Cada candidato usa el mismo plan de evaluación. El preprocessing (`SimpleImputer`, escalado y `OneHotEncoder`) vive dentro del `Pipeline`, por lo que se ajusta en cada train.

La métrica primaria se elige explícitamente: MAE, RMSE o R² en regresión; balanced accuracy, accuracy o macro F1 en clasificación; MAE o RMSE en forecasting. La selección del ganador usa esa métrica y las métricas conjuntas se calculan desde predicciones fuera de muestra. Los empates favorecen menor complejidad. Los fallos de un candidato se conservan y no detienen la referencia.

La V1 calcula permutation importance cuando hay soporte. Cada fold vuelve a ajustar el candidato ganador solo con su partición de entrenamiento y permuta exclusivamente su validación; nunca reutiliza un modelo ajustado con todo el dataset para esa explicación. Es sensibilidad predictiva, no causalidad. SHAP se anuncia como capacidad opcional y solo debe ejecutarse de manera acotada en adapters compatibles.

Los presets limitan familias y tiempo: `quick` compara referencia y modelo lineal; `recommended` añade Extra Trees y Random Forest. Datasets con soporte insuficiente degradan a diagnóstico o exploración; nunca se usa train como validación.
