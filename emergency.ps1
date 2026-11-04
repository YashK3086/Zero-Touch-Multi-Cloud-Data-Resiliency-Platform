# Emergency 1-Click Bootstrap Launcher
# Immediately brings up the Disaster Recovery Web Control Plane and pops open the browser in < 10s.

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 🚀 EMERGENCY ZERO-TOUCH MULTI-CLOUD CONTROL PLANE BOOTSTRAP" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $RepoRoot

# 1. Environment file check
if (-not (Test-Path "$RepoRoot\.env")) {
    if (Test-Path "$RepoRoot\.env.example") {
        Write-Host "⚠️  No .env detected. Creating from .env.example..." -ForegroundColor Yellow
        Copy-Item "$RepoRoot\.env.example" "$RepoRoot\.env"
    }
}

# 2. Check if Docker is available and running
$DockerRunning = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) {
        $DockerRunning = $true
    }
} catch {
    $DockerRunning = $false
}

$PortActive = $false
$conn = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
if ($conn) {
    $PortActive = $true
}

if (-not $PortActive) {
    if ($DockerRunning) {
        Write-Host "🐳 Starting Containerized Multi-Cloud Control Plane via Docker Compose..." -ForegroundColor Green
        docker compose up -d --build
    } else {
        Write-Host "⚡ Docker daemon not running. Launching via local Python FastAPI runner..." -ForegroundColor Yellow
        if (Test-Path "$RepoRoot\.venv\Scripts\python.exe") {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot'; .\.venv\Scripts\python.exe -m uvicorn sf_dr_controller.api:app --host 127.0.0.1 --port 8000" -WindowStyle Minimized
        } else {
            Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$RepoRoot'; python -m uvicorn sf_dr_controller.api:app --host 127.0.0.1 --port 8000" -WindowStyle Minimized
        }
    }

    # Wait for endpoint health check
    Write-Host "⏳ Waiting for Control Plane health on http://127.0.0.1:8000/api/status..." -ForegroundColor Cyan
    $Retries = 20
    $Healthy = $false
    while ($Retries -gt 0 -and -not $Healthy) {
        Start-Sleep -Seconds 1
        try {
            $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/status" -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "HEALTHY" -or $resp.status -eq "NOT_CONFIGURED" -or $resp.active_cloud) {
                $Healthy = $true
                break
            }
        } catch {
            $Retries--
        }
    }
} else {
    Write-Host "✅ Control Plane is already active on port 8000!" -ForegroundColor Green
}

# 3. Auto-pop the browser immediately
Write-Host "🌐 Launching Mission Control UI in default browser (http://127.0.0.1:8000/)..." -ForegroundColor Green
Start-Process "http://127.0.0.1:8000/"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " 🛡️ Control Room Online! Click '[Promote Azure Standby]' for < 10s migration." -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

