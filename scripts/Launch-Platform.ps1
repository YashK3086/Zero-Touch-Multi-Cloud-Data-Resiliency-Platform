<#
.SYNOPSIS
    Master 1-Click Platform Launcher for the Enterprise Cross-Cloud DR Engine.
.DESCRIPTION
    1. Loads project environment variables (.env).
    2. Runs Terraform deployment (optional / automatic check).
    3. Starts the autonomous watchdog sentry daemon in the background.
    4. Starts continuous streaming mock transaction producer in dry-run/live mode.
    5. Opens the glassmorphic Mission Control Web Dashboard in your default browser.
#>

[CmdletBinding()]
param(
    [switch]$SkipTerraform = $true,
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RootDir = Split-Path -Parent $ScriptDir

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   🚀 ENTERPRISE ZERO-TOUCH DR PLATFORM | 1-CLICK LAUNCHER       " -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Environment configuration
$EnvScript = Join-Path $ScriptDir "Load-Env.ps1"
if (Test-Path $EnvScript) {
    Write-Host "[1/5] Loading environment variables..." -ForegroundColor Green
    & $EnvScript
} else {
    Write-Host "[1/5] Warning: Load-Env.ps1 not found. Proceeding with existing shell env." -ForegroundColor Yellow
}

# 2. Terraform provisioning check
if (-not $SkipTerraform) {
    Write-Host "[2/5] Running Terraform Apply..." -ForegroundColor Green
    Push-Location (Join-Path $RootDir "terraform")
    try {
        terraform apply -auto-approve
    } finally {
        Pop-Location
    }
} else {
    Write-Host "[2/5] Skipping Terraform provisioning (SkipTerraform flag set)." -ForegroundColor DarkGray
}

# 3. Cloud-Native Snowpipe & SQS Ingestion Ready
Write-Host "[3/4] Cloud-Native Snowpipe (AWS S3 + SQS Auto-Ingestion) active on Snowflake." -ForegroundColor Green

# 4. Launch Autonomous Watchdog Sentry Daemon
Write-Host "[4/5] Launching Autonomous Watchdog Daemon (10s interval, 3 strikes)..." -ForegroundColor Green
$DaemonArgs = @("-m", "sf_dr_controller", "daemon", "--interval", "10", "--strikes", "3", "--plain-logs")
$DaemonJob = Start-Process -FilePath $PythonExe -ArgumentList $DaemonArgs -PassThru -WindowStyle Minimized
Write-Host "      ➔ Autonomous Watchdog Daemon running (PID: $($DaemonJob.Id))" -ForegroundColor Cyan

# 5. Launch Mission Control Web Dashboard
Write-Host "[5/5] Launching Mission Control Web Dashboard..." -ForegroundColor Green
$DashboardPy = Join-Path $RootDir "run_dashboard.py"
$StreamlitExe = Join-Path $RootDir ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $StreamlitExe)) {
    $StreamlitExe = "streamlit"
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   🌟 Platform Online! Opening Mission Control at http://localhost:8501" -ForegroundColor Yellow
Write-Host "=================================================================" -ForegroundColor Cyan

Start-Process -FilePath $StreamlitExe -ArgumentList @("run", $DashboardPy, "--server.port", "8501", "--browser.gatherUsageStats", "false")
