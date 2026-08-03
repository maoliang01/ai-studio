$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PidFile = Join-Path $ProjectRoot ".pids\frontend.pid"

if (Test-Path $PidFile) {
  $pidValue = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($pidValue -match '^\d+$') {
    Stop-Process -Id ([int]$pidValue) -Force -ErrorAction SilentlyContinue
  }
  Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

Set-Location $ProjectRoot
docker compose stop backend 2>$null
Write-Host "AI Studio services stopped."
