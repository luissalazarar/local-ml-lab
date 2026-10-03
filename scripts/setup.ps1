$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) { $env:Path = (Split-Path $candidate) + ';' + $env:Path } else { throw 'Docker no está instalado. Instala Docker Desktop y vuelve a ejecutar.' }
  }
  docker info | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Docker no está en ejecución. Abre Docker Desktop y vuelve a intentar.' }
  docker compose version | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 no está disponible.' }
  $portNumber = if ($env:APP_PORT) { [int]$env:APP_PORT } else { 3000 }
  $appUrl = "http://localhost:$portNumber"
  $port = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue
  if ($port) { throw "El puerto $portNumber está ocupado por PID $($port.OwningProcess). Define APP_PORT con otro puerto." }
  $drive = Get-PSDrive -Name ((Get-Location).Drive.Name)
  if ($drive.Free -lt 2GB) { throw 'Hay menos de 2 GiB libres; libera espacio antes de construir.' }
  docker compose up --build -d
  if ($LASTEXITCODE -ne 0) { throw 'Docker Compose no pudo construir o iniciar la aplicación.' }
  $deadline = (Get-Date).AddMinutes(8)
  $ready = $false
  do {
    try {
      $health = Invoke-RestMethod -Uri "$appUrl/api/v1/health/ready" -TimeoutSec 3
      if ($health.status -eq 'ready') { $ready = $true; break }
    } catch {}
    Start-Sleep -Seconds 3
  } while ((Get-Date) -lt $deadline)
  if (-not $ready) { throw 'La aplicación no estuvo lista dentro del tiempo esperado. Ejecuta scripts/doctor.ps1.' }
  docker compose cp scripts/smoke.py api:/app/setup-smoke.py
  if ($LASTEXITCODE -ne 0) { throw 'No se pudo copiar el smoke test al contenedor API.' }
  try {
    docker compose exec -T -e APP_URL=http://localhost:8000 api python /app/setup-smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'El smoke test sintético falló.' }
  } finally {
    docker compose exec -T api rm -f /app/setup-smoke.py
  }
  Write-Host "Laboratorio ML está verificado y disponible en $appUrl"
} finally {
  Pop-Location
}
