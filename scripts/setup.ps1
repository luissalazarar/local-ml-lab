param([switch]$InstallDocker)

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

  function Install-DockerDesktop {
    if (-not [Environment]::Is64BitOperatingSystem) {
      throw 'Docker Desktop necesita Windows de 64 bits.'
    }
    Write-Host 'Comprobando el componente WSL 2 de Windows (sin distribución Linux)…'
    $wslAvailable = Get-Command wsl.exe -ErrorAction SilentlyContinue
    if ($wslAvailable) { & wsl.exe --status *> $null }
    if (-not $wslAvailable -or $LASTEXITCODE -ne 0) {
      Write-Host 'Habilitando WSL 2 sin instalar Ubuntu ni otra distribución Linux. Windows puede mostrar una ventana UAC.'
      $wsl = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
        'wsl.exe --install --no-distribution'
      )
      if ($wsl.ExitCode -notin @(0, 3010)) { throw "No se pudo habilitar WSL 2 (código $($wsl.ExitCode))." }
      & wsl.exe --status *> $null
      if ($LASTEXITCODE -ne 0) {
        throw 'REBOOT_REQUIRED: reinicia Windows y vuelve a ejecutar scripts/setup.ps1 -InstallDocker. La autorización original sigue vigente.'
      }
    }
    & wsl.exe --update
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo actualizar WSL 2.' }
    $machine = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    $dockerArch = if ($machine -eq 'Arm64') { 'arm64' } else { 'amd64' }
    $installer = Join-Path ([IO.Path]::GetTempPath()) 'LocalMLLab-DockerDesktopInstaller.exe'
    $download = "https://desktop.docker.com/win/main/$dockerArch/Docker%20Desktop%20Installer.exe"
    Write-Host 'Descargando Docker Desktop desde Docker…'
    Invoke-WebRequest -Uri $download -OutFile $installer -UseBasicParsing
    Write-Host 'Instalando Docker Desktop con WSL 2…'
    $process = Start-Process $installer -Wait -PassThru -ArgumentList @(
      'install', '--user', '--quiet', '--accept-license', '--backend=wsl-2', '--no-windows-containers'
    )
    Remove-Item -LiteralPath $installer -Force -ErrorAction SilentlyContinue
    if ($process.ExitCode -ne 0) { throw "Docker Desktop no pudo instalarse (código $($process.ExitCode))." }
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
        if (-not $InstallDocker) {
          throw 'Docker Desktop no está instalado. Ejecuta scripts/setup.ps1 -InstallDocker.'
        }
        Install-DockerDesktop
        $candidate = Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe'
        if (-not (Test-Path -LiteralPath $candidate)) {
          throw 'Docker Desktop terminó de instalarse, pero el CLI no apareció en la ruta esperada.'
        }
        $env:Path = (Split-Path $candidate) + ';' + $env:Path
      }
    }
  }
  if (-not (Test-DockerEngine)) { Start-DockerEngine }
  docker compose version | Out-Null
  if ($LASTEXITCODE -ne 0) { throw 'Docker Compose v2 no está disponible.' }
  $portNumber = if ($env:APP_PORT) { [int]$env:APP_PORT } else { 3000 }
  $port = Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue
  $composePort = docker compose port frontend 8080 2>$null
  $ownedByThisApp = $composePort -and ($composePort -match ":$portNumber$")
  if ($port -and -not $ownedByThisApp) {
    $requestedPort = $portNumber
    $portNumber = 3001
    while (Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue) {
      $portNumber++
      if ($portNumber -gt 3099) { throw 'No hay un puerto libre entre 3001 y 3099.' }
    }
    $env:APP_PORT = [string]$portNumber
    Write-Host "El puerto $requestedPort estaba ocupado; se usará $portNumber."
  }
  $appUrl = "http://127.0.0.1:$portNumber"
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
  $buildReady = $false
  foreach ($buildAttempt in 1..3) {
    docker compose up --build -d
    if ($LASTEXITCODE -eq 0) { $buildReady = $true; break }
    if ($buildAttempt -lt 3) {
      Write-Warning "La descarga o construcción falló; reintentando ($($buildAttempt + 1) de 3)…"
      Start-Sleep -Seconds 5
    }
  }
  if (-not $buildReady) {
    throw 'La construcción falló tres veces. Revisa la conexión o proxy y vuelve a ejecutar el mismo comando; los datos se conservan.'
  }
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
  try { Start-Process $appUrl } catch { Write-Host "Abre $appUrl en tu navegador." }
} finally {
  Pop-Location
}
