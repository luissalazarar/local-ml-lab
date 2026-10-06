$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  function Test-DockerEngine {
    docker info *> $null
    return $LASTEXITCODE -eq 0
  }

  function Start-DockerEngine {
    $desktopCandidates = @(
      (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
      (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
      (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\Docker Desktop.exe')
    )
    $desktop = $desktopCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $desktop) {
      throw 'Docker Desktop no está instalado. La instalación asistida debe instalarlo desde la fuente oficial antes de ejecutar este script.'
    }
    Write-Host 'Iniciando Docker Desktop y esperando que el motor quede listo...'
    Start-Process -FilePath $desktop -WindowStyle Hidden
    $dockerDeadline = (Get-Date).AddMinutes(10)
    do {
      Start-Sleep -Seconds 5
      if (Test-DockerEngine) { return }
    } while ((Get-Date) -lt $dockerDeadline)
    throw 'Docker Desktop no pudo iniciar. Comprueba que WSL 2 y la virtualización estén habilitados; no borres los datos de Docker.'
  }

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) {
      $env:Path = (Split-Path $candidate) + ';' + $env:Path
    } else {
      $candidate = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
      if (Test-Path -LiteralPath $candidate) {
        $env:Path = (Split-Path $candidate) + ';' + $env:Path
      } else {
        throw 'Docker Desktop no está instalado. La instalación asistida debe instalarlo desde la fuente oficial antes de ejecutar este script.'
      }
    }
  }
  if (-not (Test-DockerEngine)) { Start-DockerEngine }
  docker compose version | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 no está disponible.' }
  $portNumber = if ($env:APP_PORT) { [int]$env:APP_PORT } else { 3000 }
  $appUrl = "http://127.0.0.1:$portNumber"
  $port = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue
  $composePort = docker compose port frontend 8080 2>$null
  $ownedByThisApp = $composePort -and ($composePort -match ":$portNumber$")
  if ($port -and -not $ownedByThisApp) {
    throw "El puerto $portNumber está ocupado por otro proceso (PID $($port.OwningProcess -join ', ')). Define APP_PORT con otro puerto."
  }
  $drive = Get-PSDrive -Name ((Get-Location).Drive.Name)
  if ($drive.Free -lt 2GB) { throw 'Hay menos de 2 GiB libres; libera espacio antes de construir.' }
  $avastRoot = @(
    Get-ChildItem Cert:\LocalMachine\Root, Cert:\CurrentUser\Root -ErrorAction SilentlyContinue |
      Where-Object { $_.Subject -like '*Avast Web/Mail Shield Root*' }
  )
  if ($avastRoot.Count -gt 0) {
    Write-Warning 'Avast HTTPS inspection detectada. La excepcion TLS se aplicara solo a esta construccion local.'
    if (-not $env:UV_INSECURE_HOST) { $env:UV_INSECURE_HOST = 'pypi.org files.pythonhosted.org' }
    if (-not $env:NPM_CONFIG_STRICT_SSL) { $env:NPM_CONFIG_STRICT_SSL = 'false' }
  }
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
