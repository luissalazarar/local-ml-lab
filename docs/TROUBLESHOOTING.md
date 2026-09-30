# Solución de problemas

- Puerto ocupado: cambia `APP_PORT` en `.env`, por ejemplo `APP_PORT=3001`.
- Docker no inicia: abre Docker Desktop, confirma WSL 2 y reinicia Windows si el instalador lo solicita.
- Worker no disponible: `docker compose logs --tail=100 worker queue`.
- Poco espacio: revisa artifacts desde la interfaz; no borres el volumen como arreglo de arranque.
- Resultado no evaluable: revisa soporte de clases, filas etiquetadas y alcance. No significa que el job haya fallado.
- Error TLS cuyo emisor sea `Avast Web/Mail Shield Root`: la inspección HTTPS de Avast está reemplazando el certificado dentro de Docker. La solución preferida es pausar la inspección HTTPS durante la construcción o instalar esa CA en las imágenes. Como excepción temporal para una construcción local puedes ejecutar en PowerShell `$env:NPM_CONFIG_STRICT_SSL='false'; $env:UV_INSECURE_HOST='pypi.org files.pythonhosted.org'; docker compose build`; no guardes esas variables en `.env` ni las uses en CI.
