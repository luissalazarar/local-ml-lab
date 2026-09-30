# Identidad visual de Laboratorio ML

## Marca y autoría

- Nombre visible: **Laboratorio ML**.
- Autoría: **Desarrollado por Luis Salazar**.
- El nombre enlaza al inicio. La autoría enlaza de forma independiente al perfil público de LinkedIn y no carga widgets, trackers ni recursos de LinkedIn.
- `LM` es un distintivo tipográfico de la aplicación, no un logotipo de SARE.

## Paleta original de referencia

Los siguientes colores proceden de los HEX indicados en el manual de referencia. El repositorio no incluye el manual ni sus activos.

| Uso | HEX |
| --- | --- |
| Azul petróleo | `#054D61` |
| Turquesa | `#049990` |
| Gris claro | `#EDEDED` |
| Negro | `#000000` |
| Naranja | `#EB5B27` |
| Azul | `#0871B8` |

## Tokens derivados para la interfaz

Los tonos siguientes no se presentan como colores originales del manual. Son decisiones de interfaz para fondos, estados y contraste.

- Azul petróleo oscuro `#033B4B`: hover del botón principal.
- Turquesa oscuro `#03746E`: apoyo en estados interactivos.
- Tinte turquesa `#E1F5F3`: selección y fondos informativos suaves.
- Texto principal `#12313A` y texto secundario `#52666C`.
- Fondo de página `#F6F9F9` y división `#D5DEE0`.
- Estados: éxito `#176B4B`, advertencia `#8A390E`, error `#A1261C` e información `#075E99`, cada uno acompañado por texto o etiqueta.

El botón principal usa azul petróleo con texto blanco. Turquesa y naranja se reservan para acentos, datos y avisos; no se usa texto blanco pequeño sobre esos colores.

## Tipografía

La familia solicitada es Mont. Se recibieron archivos TTF con pesos Regular, SemiBold y Bold, pero no se recibió una licencia o autorización verificable para redistribuirlos en este repositorio o incrustarlos en artifacts. Por ese motivo:

- los archivos no se copiaron ni se publicaron;
- la aplicación intenta usar una instalación local llamada `Mont` si el sistema ya la ofrece;
- el fallback explícito es `ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif`;
- PDF usa Helvetica incluida en el entorno Docker para no depender de fuentes instaladas en la Mac;
- Excel no incrusta fuentes.

Mont permanece **pendiente de una licencia de webfont y redistribución compatible con GitHub, Docker, PDF y las entregas previstas**. Una autorización adecuada debe indicar, como mínimo, si permite alojar los archivos con la aplicación, convertirlos a WOFF2 y, si corresponde, incrustarlos en PDF.

Jerarquía aplicada:

- texto, formularios y controles: 16 px con interlineado cercano a 1.5;
- ayudas y autoría: 13 px o más;
- tablas: 14–16 px;
- títulos internos: 32–40 px adaptables;
- hero: hasta 56 px en escritorio;
- métricas: 28–32 px con números tabulares.

## Uso de datos y estados

- Azul petróleo: marca, títulos y acción principal.
- Turquesa: selección, histórico observado y puntos de regresión.
- Azul: enlaces, información y validación de selección.
- Naranja: pronóstico futuro y advertencias.
- Los estados siempre incluyen texto, forma, trazo o etiqueta además del color.
