$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
  $ok = $true
  function Check($name, $action) {
    try {
      & $action
      Write-Host "[OK] $name"
    } catch {
      Write-Host "[ERROR] $name - $($_.Exception.Message)"
      $script:ok = $false
    }
  }

  if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
    if (Test-Path -LiteralPath $candidate) {
      $env:Path = (Split-Path $candidate) + ';' + $env:Path
    }
  }
  $portNumber = if ($env:APP_PORT) { [int]$env:APP_PORT } else { 3000 }
  $appUrl = "http://127.0.0.1:$portNumber"
  Check 'Docker Engine' { docker version | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'motor no disponible' } }
  Check 'Docker Compose' { docker compose version | Out-Null; if ($LASTEXITCODE -ne 0) { throw 'Compose v2 no disponible' } }
  Check 'Configuración Compose' { docker compose config --quiet; if ($LASTEXITCODE -ne 0) { throw 'configuración inválida' } }
  Check 'API' { if ((Invoke-RestMethod "$appUrl/api/v1/health/ready" -TimeoutSec 4).status -ne 'ready') { throw 'API no lista' } }
  Check 'Sistema' { Invoke-RestMethod "$appUrl/api/v1/system" -TimeoutSec 4 | ConvertTo-Json }
  $drive = Get-PSDrive -Name ((Get-Location).Drive.Name)
  Write-Host ("[INFO] Espacio libre: {0:N1} GiB" -f ($drive.Free / 1GB))
  docker compose ps
  if ($ok) { exit 0 } else { exit 1 }
} finally {
  Pop-Location
}
