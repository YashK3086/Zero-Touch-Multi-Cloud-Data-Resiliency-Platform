<#
.SYNOPSIS
  One-command automated deployment for the entire Zero-Touch Multi-Cloud DR Platform.
.USAGE
  .\scripts\Deploy-All.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   ZERO-TOUCH MULTI-CLOUD DATA RESILIENCY PLATFORM        " -ForegroundColor Cyan
Write-Host "   Single-Command Automated Infrastructure Deployment    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Load environment secrets
Write-Host "`n[1/3] Loading multi-cloud credentials from .env..." -ForegroundColor Yellow
. .\scripts\Load-Env.ps1 -Quiet
Write-Host "Credentials mapped for AWS, Azure, and Snowflake." -ForegroundColor Green

# 2. Change into terraform directory
Push-Location "$PSScriptRoot\..\terraform"

try {
    # 3. Execute Terraform Apply
    Write-Host "`n[2/3] Executing 'terraform apply -auto-approve'..." -ForegroundColor Yellow
    terraform apply -auto-approve
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform apply failed with exit code $LASTEXITCODE"
    }

    Write-Host "`n[3/3] Deployment complete! Verifying outputs..." -ForegroundColor Green
    terraform output
}
finally {
    Pop-Location
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host " All 20 Multi-Cloud Resources Successfully Provisioned!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan
