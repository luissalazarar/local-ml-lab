# Agregar modelos

1. Crear un adapter registrado con ID estable, tareas, complejidad, requisitos, defaults y espacio acotado.
2. Elegir preprocessing compatible con sparse/dense y mantenerlo dentro del pipeline.
3. No observar holdout, categorías, medianas ni target de validación durante fit.
4. Respetar el universo completo de clases y verificar probabilidades.
5. Manejar elegibilidad, timeout y fallo sin abortar otros candidatos.
6. Añadir pruebas de shapes, clases ausentes, categoría nueva, splits compartidos y baseline ganador.
7. Revisar licencia y no introducir llamadas externas.

