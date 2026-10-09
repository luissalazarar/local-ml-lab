# Solución de problemas

- Puerto ocupado: cambia `APP_PORT` en `.env`, por ejemplo `APP_PORT=3001`.
- Docker no inicia en Windows: abre Docker Desktop, confirma el componente WSL 2 y reinicia si el instalador lo solicita; Laboratorio ML no necesita Ubuntu ni otra distribución Linux.
- Docker no inicia en macOS: abre Docker Desktop y espera a que el motor quede listo; WSL no aplica.
- Docker no inicia en Linux: confirma Docker Engine y el plugin Compose de tu distribución; Docker Desktop y WSL no aplican.
- Worker no disponible: `docker compose logs --tail=100 worker queue`.
- Poco espacio: revisa artifacts desde la interfaz; no borres el volumen como arreglo de arranque.
- Resultado no evaluable: revisa soporte de clases, filas etiquetadas y alcance. No significa que el job haya fallado.
- Error TLS cuyo emisor sea `Avast Web/Mail Shield Root`: los instaladores de Windows y macOS detectan ese certificado y limitan la excepción a su proceso de construcción; no la guardan en `.env`, imágenes ni CI. La solución más estricta sigue siendo pausar la inspección HTTPS de Avast durante la primera construcción o instalar su CA en las imágenes. Para una ejecución manual excepcional puedes usar en PowerShell `$env:NPM_CONFIG_STRICT_SSL='false'; $env:UV_INSECURE_HOST='pypi.org files.pythonhosted.org'; docker compose build`; no persistas esas variables.
