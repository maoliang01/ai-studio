$ErrorActionPreference = "Continue"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$LogRoot = Join-Path $ProjectRoot "logs"
$PidRoot = Join-Path $ProjectRoot ".pids"
$FrontendLog = Join-Path $LogRoot "frontend.log"
$FrontendErrorLog = Join-Path $LogRoot "frontend.err.log"

New-Item -ItemType Directory -Force -Path $LogRoot, $PidRoot | Out-Null
Set-Location $ProjectRoot

function Test-Port([int]$Port) {
  return $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

Write-Host "Starting AI Studio..." -ForegroundColor Cyan

$dockerInfo = docker info 2>$null
if ($LASTEXITCODE -ne 0) {
  throw "Docker engine is unavailable. Start Docker Desktop and run this script again."
}

Write-Host "Preparing the shared Docker network..." -ForegroundColor Yellow
$networkExists = docker network inspect ai-studio-network 2>$null
if ($LASTEXITCODE -ne 0) {
  docker network create ai-studio-network | Out-Null
}

$dbExists = docker container inspect ai-studio-db 2>$null
if ($LASTEXITCODE -eq 0) {
  $networkMembers = docker network inspect ai-studio-network --format '{{range .Containers}}{{.Name}} {{end}}'
  if ($networkMembers -notmatch '(^|\s)ai-studio-db(\s|$)') {
    docker network connect --alias db ai-studio-network ai-studio-db
  }
  docker start ai-studio-db 2>$null | Out-Null
} else {
  docker compose up -d db
}

Write-Host "Starting Neo4j and the backend container..." -ForegroundColor Yellow
$neo4jExists = docker container inspect neo4j-ai-studio 2>$null
if ($LASTEXITCODE -eq 0) {
  docker start neo4j-ai-studio 2>$null | Out-Null
} else {
  docker compose up -d --no-deps neo4j
}
docker compose up -d --no-deps backend
if ($LASTEXITCODE -ne 0) {
  throw "Docker Compose could not start the backend. Run: docker compose logs --tail 80 backend"
}

$backendReady = $false
for ($i = 0; $i -lt 60; $i++) {
  if (Test-Port 8500) {
    try {
      $response = Invoke-WebRequest "http://localhost:8500/docs" -UseBasicParsing -TimeoutSec 3
      if ($response.StatusCode -eq 200) {
        $backendReady = $true
        break
      }
    } catch { }
  }
  Start-Sleep -Seconds 2
}

if (-not $backendReady) {
  docker compose logs --tail 80 backend
  throw "Backend did not become ready."
}

if (-not (Test-Port 3000)) {
  Write-Host "Starting the Next.js frontend..." -ForegroundColor Yellow
  $frontend = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $FrontendRoot `
    -RedirectStandardOutput $FrontendLog `
    -RedirectStandardError $FrontendErrorLog `
    -WindowStyle Hidden `
    -PassThru
  Set-Content -Path (Join-Path $PidRoot "frontend.pid") -Value $frontend.Id
} else {
  Write-Host "Frontend is already listening on port 3000."
}

$frontendReady = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $response = Invoke-WebRequest "http://localhost:3000" -UseBasicParsing -TimeoutSec 3
    if ($response.StatusCode -eq 200) {
      $frontendReady = $true
      break
    }
  } catch { }
  Start-Sleep -Seconds 2
}

if (-not $frontendReady) {
  Get-Content $FrontendErrorLog -Tail 80 -ErrorAction SilentlyContinue
  throw "Frontend did not become ready."
}

Write-Host ""
Write-Host "AI Studio is ready." -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000"
Write-Host "Backend:  http://localhost:8500/docs"
Write-Host "Neo4j:    http://localhost:7474"
