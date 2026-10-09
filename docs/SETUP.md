# Instalación

Para uso normal ejecuta `sh scripts/setup.sh` en macOS/Linux o
`powershell -ExecutionPolicy Bypass -File scripts/setup.ps1` en Windows y abre
`http://127.0.0.1:3000`.

La única dependencia de ejecución en el host es un motor Docker con Compose v2. En Windows y
macOS, Docker Desktop es la ruta más simple porque incluye motor, CLI y Compose. El backend de
contenedores Linux usado en Windows necesita el componente WSL 2, pero no una distribución como
Ubuntu; el instalador usa `wsl.exe --install --no-distribution`. macOS no usa WSL. Linux usa Docker
Engine con el plugin Compose de su propia distribución, sin Docker Desktop ni WSL. Git es opcional
y Python y Node se ejecutan dentro de Docker.

Ambos instaladores son idempotentes: pueden ejecutarse de nuevo, inician Docker Desktop cuando
está cerrado, respetan un stack existente, construyen Compose, esperan healthchecks y ejecutan el
smoke sintético sin borrar volúmenes. Si el puerto pertenece a otra aplicación, explican cómo usar
`APP_PORT=3001`. Las comprobaciones usan la dirección IPv4 que Compose publica para evitar que un
servicio distinto ligado a `localhost` por IPv6 intercepte la navegación.

Los entrypoints Linux se normalizan a LF tanto en Git como durante la imagen, por lo que un
checkout Windows no rompe el arranque y el mismo repositorio funciona en macOS Apple Silicon. Si
Avast intercepta HTTPS, los instaladores detectan su certificado y limitan la excepción TLS al
proceso de construcción local; no se guarda en `.env`, imágenes ni CI.

La CI construye y prueba imágenes Linux amd64. En Windows se verificaron físicamente el arranque y
uso local el 05-10-2026 en un ASUS ROG Strix G16 G614JIR con Intel Core i9-14900HX y NVIDIA RTX
4070; es evidencia de ese equipo, no compatibilidad universal con Windows. La sección «Instalación
asistida por IA» del [README](../README.md) define una sola autorización global para todos los
prerequisitos y pasos posteriores.
