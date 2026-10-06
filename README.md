# Laboratorio ML · v0.7.0001

¿Tienes un Excel y quieres probar machine learning, pero no sabes por dónde empezar?

Sube tu data, dinos qué quieres estimar o entender y la aplicación revisará su calidad, preparará las variables, comparará modelos y te explicará los resultados.

El análisis corre localmente en tu equipo y no necesitas una API key.

La identidad visual (símbolo, variantes y tamaños de uso), los tokens y el estado de licencia de Mont están documentados en [Identidad visual](docs/VISUAL_IDENTITY.md).

## Qué puedes hacer

- Explorar Excel (.xlsx), CSV y Parquet con tipos primitivos. Excel es el camino principal.
- Crear versiones preparadas auditables con un editor guiado por columna, preview antes/después, filas apartadas y receta reutilizable.
- Estimar un valor, predecir categorías o pronosticar una serie mensual regular.
- Comparar referencias simples, modelos lineales y árboles con particiones congeladas, confirmación secundaria cuando aplica y una política conservadora.
- Observar candidatos, métricas, trayectorias y gráficos reales por evaluación mientras el run continúa; después se puede reproducir el recorrido sin reentrenar.
- Revisar calidad, exclusiones, métricas, candidatos fallidos y límites.
- Explorar variables numéricas con correlaciones, scatterplots y boxplots calculados localmente sobre una muestra determinista.
- Ver qué variables aportaron más a la predicción y probar escenarios interactivos con la forma real del modelo seleccionado, lineal o no lineal, dentro de los rangos observados.
- Exportar Excel, PDF y contexto TXT/Markdown/JSON para cualquier IA.
- Reabrir el historial persistente después de reiniciar.

## Demo visual

Capturas tomadas de la instalación Docker verificada, sin mockups:

![Inicio de Laboratorio ML](docs/screenshots/home.png)

![Preparación guiada de columnas](docs/screenshots/preparation.png)

![Análisis LIVE con evidencia persistida](docs/screenshots/live-analysis.png)

![Resultado real de regresión](docs/screenshots/regression-result.png)

![Resultado real de pronóstico](docs/screenshots/forecast-result.png)

![Inicio móvil de Laboratorio ML](docs/screenshots/mobile-home.png)

## Quick start

Solo requiere un motor Docker en ejecución con Compose v2 y al menos 4 GiB disponibles para la primera construcción. En Windows y macOS, la opción más simple es Docker Desktop porque ya incluye el motor, el CLI y Compose. En Linux basta Docker Engine con el plugin Compose. El instalador levanta los servicios y ejecuta una prueba sintética completa; Python y Node quedan dentro de Docker.

macOS/Linux:

```bash
sh scripts/setup.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Abre [http://127.0.0.1:3000](http://127.0.0.1:3000). Usamos la dirección IPv4 publicada por Compose para evitar que otra aplicación ligada a `localhost` por IPv6 intercepte la navegación. No hace falta `.env`, Python, Node, Git ni OpenAI. Git es opcional porque el repositorio también puede obtenerse como ZIP. Los scripts no cambian la política global de PowerShell ni borran datos. Consulta estado con `docker compose ps`; apaga sin borrar datos con `docker compose down`. Si el puerto 3000 está ocupado, define `APP_PORT` antes de ejecutar el instalador.

## Instalación asistida por IA

Puedes pedirle a tu asistente de IA (Claude, ChatGPT, Codex, Gemini…) que obtenga este repositorio y lo deje funcionando. Pásale la URL del repo y el prompt de abajo. **No necesitas tener nada instalado de antemano.**

### Contrato de una sola confirmación

El asistente debe revisar primero el equipo y presentar **una sola pregunta**: si autorizas instalar y configurar todo lo necesario hasta dejar Laboratorio ML listo. Esa pregunta debe mencionar que puede incluir WSL 2 en Windows, Docker Desktop o Docker Engine con Compose, elevación administrativa, aceptación de los términos del instalador oficial y un reinicio del sistema. Debe escoger la ruta mínima y no instalar Git, Python o Node si no son necesarios.

Si respondes que sí, esa autorización permanece vigente durante toda la instalación. El asistente no debe volver a pedir permiso para cada comando, instalación, arranque, reintento o comprobación. Debe ejecutar todo lo que su entorno le permita, iniciar Docker Desktop por su cuenta, esperar al motor, continuar hasta ejecutar el smoke y abrir la aplicación. No debe detenerse solo para decirte que abras Docker manualmente.

Las ventanas protegidas del sistema operativo (UAC, contraseña de administrador o avisos de seguridad) no pueden omitirse: el asistente debe advertirte que las aceptes cuando aparezcan, sin convertir cada una en una nueva pregunta de autorización. Si Windows necesita reiniciarse, debe dejar registrado el siguiente paso, reiniciar si tiene capacidad para hacerlo y retomar al volver. Si la conversación no puede reanudarse sola, tu mensaje `continúa` o `ya reinicié` solo reanuda la autorización original; no debe pedir otra confirmación.

La autorización se limita a esta instalación: no permite borrar datos existentes, desactivar controles de seguridad, usar descargas no oficiales ni modificar el código salvo una incompatibilidad necesaria y explicada.

Qué debe hacer, en orden:

1. **Revisar y pedir una sola autorización.** Comprobar el sistema operativo, arquitectura, permisos, memoria, puerto, WSL 2 cuando sea Windows y, sobre todo, si hay un motor Docker activo con Compose v2 (`docker info` y `docker compose version`). El CLI de Docker sin motor no es suficiente. Presentar juntos todos los faltantes previsibles y hacer la pregunta global descrita arriba.
2. Tras el `sí`, instalar solo lo mínimo desde fuentes oficiales (Docker: https://docs.docker.com/get-started/get-docker/ · WSL: https://learn.microsoft.com/windows/wsl/install). En Windows, usar WSL 2 y Docker Desktop. En macOS, usar Docker Desktop para Apple Silicon o Intel. En Linux, usar Docker Engine y el plugin Compose. Docker Desktop ya incluye motor, CLI y Compose: no instalar esas piezas por separado. Reiniciar si es obligatorio, abrir Docker Desktop mediante comando y esperar hasta que `docker info` responda. Resolver por sí mismo un puerto ocupado eligiendo otro libre.
3. Obtener el repositorio. Si ya existe Git, usar `git clone`; si no existe, descargar y extraer el ZIP con las herramientas incluidas en el sistema. No instalar Git solo para este paso.
4. Ejecutar el instalador del Quick start correspondiente. No crear `.env` salvo que sea necesario para usar otro puerto. La primera construcción descarga imágenes y puede tardar varios minutos.
5. Confirmar que el instalador termina con el smoke sintético en `healthy`; ese smoke recorre regresión, clasificación y pronóstico, abre XLSX/PDF y comprueba persistencia y ausencia de muestras privadas. Si falla, diagnosticar y reintentar sin borrar volúmenes ni volver a solicitar permiso.
6. Ejecutar `docker compose ps`, comprobar frontend, API, worker y queue saludables y abrir la URL final. Python es opcional y no se necesita OpenAI ni ninguna API key.

Al terminar debe informar `status`, `app_url`, `services_checked`, `smoke_result`, `changes_made`, `limitations` y `next_action`, sin decir «saludable» si solo validó Compose. Si una encolación falla, la API responde `503` con el `job_id`; el outbox SQLite la recupera cuando vuelve la cola, y no debe borrar volúmenes para resolverlo. Para una validación más completa también existen `python3 scripts/cancel_smoke.py` y `scripts/recovery_smoke.py`.

Prompt para tu asistente:

> Obtén este repositorio usando la URL que acompaña esta solicitud y déjalo completamente funcionando, aunque no haya nada instalado. Lee todo el README y cumple la sección «Instalación asistida por IA». Inspecciona primero el equipo y luego hazme una sola pregunta para autorizar, en conjunto, la instalación y configuración de los prerequisitos oficiales mínimos, incluida elevación administrativa, términos del instalador y reinicio si corresponde. Cuando responda sí, no vuelvas a pedirme permiso. En Windows instala WSL 2 y Docker Desktop solo si faltan; en macOS instala Docker Desktop solo si falta; en Linux instala Docker Engine y Compose solo si faltan. Docker Desktop ya incluye motor, CLI y Compose. No instales Git, Python ni Node: si no hay Git, descarga el ZIP con las herramientas del sistema, y ejecuta Python y Node dentro de Docker. Abre Docker por tu cuenta, espera a que el motor esté listo, elige otro puerto si hace falta, ejecuta el instalador, completa el smoke y abre la aplicación. Si aparece una ventana protegida del sistema, indícame que la acepte; eso no inicia una nueva ronda de autorización. Si un reinicio interrumpe la conversación, conserva el siguiente paso y continúa con la autorización original cuando vuelva. No borres datos, no desactives seguridad y no uses descargas no oficiales. No termines hasta que la aplicación esté lista o exista un bloqueo externo concreto que no puedas resolver. Al final informa la URL, servicios comprobados, smoke ejecutado, cambios y limitaciones reales.

## Flujo de uso

1. Sube tu Excel o archivo de datos, o elige uno de los seis ejemplos sintéticos.
2. Revisa cómo se interpretaron columnas, faltantes, IDs y duplicados.
3. En **Preparar**, revisa una columna a la vez, confirma qué contiene, para qué sirve y cómo interpretarla; el original no cambia.
4. Elige el resultado que quieres predecir; para pronóstico, también fecha, horizonte y, solo si corresponde, agregación mensual.
5. Revisa el preflight y ejecuta.
6. Observa evaluaciones reales en vivo y después compara selección, prueba reservada, referencia, métricas y drivers; en regresión o clasificación puedes mover entradas y en pronóstico recorrer el horizonte ya calculado, sin modificar la corrida.

El flujo es **Original → Preparado → Análisis → Entrenamiento**. Preparar no significa que Laboratorio ML pueda saber si tus datos son correctos para tu negocio. Las transformaciones que aprenden de los datos continúan ocurriendo únicamente dentro del entrenamiento para evitar fugas.

La confiabilidad resume la solidez de la evaluación; no es una probabilidad de acierto. Una referencia sencilla puede ganar cuando la mejora no alcanza magnitud y consistencia suficientes. La importancia se calcula fuera del train de cada fold, no decide retrospectivamente el ganador y no demuestra causalidad.

## Privacidad y OpenAI opcional

El núcleo funciona offline después de descargar imágenes y dependencias. Los archivos viven en el volumen Docker local. No hay trackers ni salida externa por defecto. La vista previa y copia del contexto offline están disponibles; esta versión todavía no realiza envíos directos a OpenAI ni almacena API keys.

## Exportaciones

El Excel preparado contiene datos activos, filas apartadas, transformaciones, comparación de calidad y diccionario en lenguaje humano. Los reportes del análisis explican Original, Preparado, Análisis y Entrenamiento. Todos nacen de snapshots inmutables.

## Limitaciones y qué no hace

V1 no combina tablas, reproduce Power Query, hace pivots, fuzzy dedupe ni elimina outliers automáticamente. Tampoco ofrece inferencia por lotes, clustering, calibración formal, intervalos conformales, SHAP, tuning Optuna completo, GPU, deep learning, multiusuario, despliegue público ni causalidad. El simulador interactivo proyecta con un reajuste local del modelo seleccionado dentro de rangos observados: no es una nueva evaluación, una intervención causal ni una garantía futura. Forecasting acepta una sola serie mensual regular sin covariables; exige calendario continuo, no rellena huecos y permite sumar o promediar observaciones del mes solo para ese análisis. La validación tabular supone registros independientes: grupos, entidades repetidas y usos temporales no están soportados. Consulta [ROADMAP](docs/ROADMAP.md).

## Probar sin usar tus propios datos

La pantalla de ejemplos ofrece seis recorridos Excel-first. El sexto enseña a preparar una fecha DMY, un monto con coma decimal, un ID, espacios, faltantes y un duplicado exacto antes de una regresión. Cada workbook tiene una hoja `Datos` y una hoja `Guía`; la configuración recomendada se muestra antes de ejecutar y puede modificarse.

`examples/` contiene únicamente datos sintéticos reproducibles con semilla fija. CSV y Parquet se conservan para pruebas de formato y CI. Regenera los archivos con `cd backend && uv run python ../scripts/generate_examples.py`.

## Excel y formatos soportados

La estructura recomendada es una tabla con una fila por observación, una columna por variable y encabezados claros. Puedes elegir hoja y fila real de encabezados. La app no interpreta diseño visual, no ejecuta macros ni corrige automáticamente todos los errores de la data. `.xls` antiguo no está soportado; guárdalo como `.xlsx` desde Excel antes de subirlo.

## Datasets públicos para seguir practicando

El Home, el primer paso y la sección [Guía](http://127.0.0.1:3000/guide#datasets) enlazan UCI y la Plataforma Nacional de Datos Abiertos del Perú. Son referencias externas: la app no descarga ni envía datos automáticamente y ningún dataset está garantizado para funcionar sin preparación.

## Versión

`version.json` es la fuente de verdad de la release visible `MAJOR.MINOR.BUILD`; BUILD usa cuatro dígitos. Su `semver` se sincroniza con los paquetes backend y frontend. MAJOR requiere una generación incompatible aprobada, MINOR agrega una feature compatible y BUILD corrige de forma compatible. Los cambios solo documentales no publican versión. Verifica mirrors con `python3 scripts/check_version.py`.

## FAQ

**¿Necesito saber machine learning?** No. El wizard parte de tu pregunta y explica los términos.

**¿Necesito una API key?** No. Esta versión no envía datos directamente a OpenAI.

**¿Mis datos salen del equipo?** No. La aplicación genera una proyección revisable para que decidas si la copias a otra herramienta.

**¿Por qué ganó una referencia sencilla?** Porque ningún candidato completo superó la mejora práctica mínima y el gate de consistencia. Esto no demuestra que no exista señal.

**¿Por qué no hay R² o ROC?** Algunas métricas no son válidas con un resultado constante, una sola clase o soporte insuficiente; se muestran como no disponibles con motivo.

**¿Por qué no aparecen bandas?** Requieren calibración separada y suficientes errores históricos por horizonte.

**¿Qué significa poca data?** Que hay pocas observaciones para comprobar si el patrón se repite; el resultado se marca exploratorio.

**¿Por qué se excluyó una columna?** IDs, texto libre, columnas vacías/constantes o variables no disponibles pueden excluirse con un motivo auditable.

**¿Importancia significa causalidad?** No. Solo indica ayuda predictiva bajo esa evaluación.

**¿Por qué una accuracy alta puede engañar?** Acertar siempre la clase frecuente puede ignorar por completo la minoritaria.

**¿Puedo cerrar el navegador?** Sí. El worker continúa y el progreso se recupera desde eventos persistentes.

**¿Cómo recupero el historial?** Abre Historial; el volumen persiste tras `docker compose down`.

**¿Cómo borro mis datos?** En Estado puedes borrar elementos por separado o usar **Borrar datos guardados** para eliminar uploads, versiones, corridas, reportes e historial de una sola vez. La acción pide confirmación, se bloquea si existen trabajos activos y conserva la aplicación, su configuración y la estructura de almacenamiento.

**¿Qué ocurre si se cancela un modelo?** El worker termina el proceso de análisis y sus descendientes dentro de un límite acotado. El job queda `cancelled`, no `failed`, y nunca publica un parcial como completo.

**¿Evaluación y forecast futuro son lo mismo?** No. Evaluación compara contra datos conocidos fuera de train; forecast futuro no tiene valor real disponible todavía.

## Diagnóstico, desarrollo y contribución

Ejecuta `scripts/doctor.ps1` o `scripts/doctor.sh`. Para instalación y pruebas, consulta [SETUP](docs/SETUP.md), [TESTING](docs/TESTING.md) y [TROUBLESHOOTING](docs/TROUBLESHOOTING.md). Las contribuciones siguen [CONTRIBUTING.md](CONTRIBUTING.md). Licencia MIT para el código original; dependencias conservan sus licencias.

## Plataformas verificadas

- macOS Apple Silicon (`arm64`, Apple M1): build, Compose, regresión, clasificación, forecast, cancelación, exportaciones y reinicio verificados el 30-09-2026.
- Linux `amd64`: verificado por CI en cada PR/push a `master`.
- Windows — ASUS ROG Strix G16 G614JIR (Intel Core i9-14900HX, NVIDIA RTX 4070): arranque y uso local verificados físicamente por el autor el 04-10-2026. Es evidencia de ese equipo, no una declaración de compatibilidad universal con Windows.

El cierre reproducible de cada hallazgo está en [AUDIT_2026-09-30](docs/AUDIT_2026-09-30.md).
