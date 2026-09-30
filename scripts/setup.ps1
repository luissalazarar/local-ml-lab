$ErrorActionPreference = 'Stop'
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
  $candidate = 'C:\Program Files\Docker\Docker\resources\bin\docker.exe'
  if (Test-Path -LiteralPath $candidate) { $env:Path = (Split-Path $candidate) + ';' + $env:Path } else { throw 'Docker no está instalado. Instala Docker Desktop y vuelve a ejecutar.' }
}
docker version | Out-Null
docker compose version | Out-Null
$port = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($port) { throw "El puerto 3000 está ocupado por PID $($port.OwningProcess). Cambia APP_PORT." }
$drive = Get-PSDrive -Name ((Get-Location).Drive.Name)
if ($drive.Free -lt 2GB) { throw 'Hay menos de 2 GiB libres; libera espacio antes de construir.' }
docker compose up --build -d
$deadline = (Get-Date).AddMinutes(8)
do {
  try { $health = Invoke-RestMethod -Uri 'http://localhost:3000/api/v1/health/ready' -TimeoutSec 3; if ($health.status -eq 'ready') { break } } catch {}
  Start-Sleep -Seconds 3
} while ((Get-Date) -lt $deadline)
if ($health.status -ne 'ready') { throw 'La aplicación no estuvo lista dentro del tiempo esperado. Ejecuta scripts/doctor.ps1.' }
Write-Host 'Laboratorio ML está disponible en http://localhost:3000'

