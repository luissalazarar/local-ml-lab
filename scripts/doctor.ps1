$ErrorActionPreference = 'Continue'
$ok = $true
function Check($name, $action) { try { & $action; Write-Host "[OK] $name" } catch { Write-Host "[ERROR] $name - $($_.Exception.Message)"; $script:ok = $false } }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { $env:Path = 'C:\Program Files\Docker\Docker\resources\bin;' + $env:Path }
Check 'Docker Engine' { docker version | Out-Null }
Check 'Docker Compose' { docker compose version | Out-Null }
Check 'Configuración Compose' { docker compose config --quiet }
Check 'API' { if ((Invoke-RestMethod 'http://localhost:3000/api/v1/health/ready' -TimeoutSec 4).status -ne 'ready') { throw 'API no lista' } }
Check 'Sistema' { Invoke-RestMethod 'http://localhost:3000/api/v1/system' -TimeoutSec 4 | ConvertTo-Json }
$drive = Get-PSDrive -Name ((Get-Location).Drive.Name); Write-Host ("[INFO] Espacio libre: {0:N1} GiB" -f ($drive.Free / 1GB))
docker compose ps
if ($ok) { exit 0 } else { exit 1 }

