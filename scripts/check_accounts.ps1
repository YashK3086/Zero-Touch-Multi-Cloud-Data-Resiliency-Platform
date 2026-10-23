<#
.SYNOPSIS
  Checks live status of AWS, Azure, and Snowflake accounts without printing secrets.
.USAGE
  .\scripts\check_accounts.ps1
#>
$ErrorActionPreference = 'Continue'
$envFile = Join-Path $PSScriptRoot '..\.env'
if (-not (Test-Path $envFile)) { throw ".env file not found at $envFile" }

$cfg = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') {
        $cfg[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  MULTI-CLOUD ACCOUNT CONNECTIVITY AUDIT  " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. AWS
Write-Host "`n[1/3] AWS Cloud Health:" -ForegroundColor Yellow
$env:AWS_ACCESS_KEY_ID = $cfg['AWS_ACCESS_KEY_ID']
$env:AWS_SECRET_ACCESS_KEY = $cfg['AWS_SECRET_ACCESS_KEY']
$env:AWS_DEFAULT_REGION = if ($cfg['AWS_REGION']) { $cfg['AWS_REGION'] } else { 'us-east-1' }

$awsId = aws sts get-caller-identity --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    $j = $awsId | ConvertFrom-Json
    Write-Host "  [OK] AWS Authenticated: Account $($j.Account), ARN: $($j.Arn)" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] AWS STS error: $awsId" -ForegroundColor Red
}

# 2. Azure
Write-Host "`n[2/3] Azure Cloud Health:" -ForegroundColor Yellow
try {
    $tok = Invoke-RestMethod -Method Post -Uri "https://login.microsoftonline.com/$($cfg['AZURE_TENANT_ID'])/oauth2/v2.0/token" -Body @{
        client_id     = $cfg['AZURE_CLIENT_ID']
        client_secret = $cfg['AZURE_CLIENT_SECRET']
        scope         = 'https://management.azure.com/.default'
        grant_type    = 'client_credentials'
    }
    Write-Host "  [OK] Service Principal OAuth Token acquired." -ForegroundColor Green
    $h = @{ Authorization = "Bearer $($tok.access_token)" }

    $subId = $cfg['AZURE_SUBSCRIPTION_ID']
    try {
        $sub = Invoke-RestMethod -Headers $h -Uri "https://management.azure.com/subscriptions/$subId`?api-version=2022-12-01"
        Write-Host "  [OK] Subscription '$($sub.displayName)' (State: $($sub.state))" -ForegroundColor Green
    } catch {
        Write-Host "  [WARN] Subscription $subId not accessible: $($_.Exception.Message)" -ForegroundColor Red
        # List all visible subscriptions for this SP
        $allSubs = Invoke-RestMethod -Headers $h -Uri "https://management.azure.com/subscriptions?api-version=2022-12-01"
        Write-Host "         Visible subscriptions count: $($allSubs.value.Count)" -ForegroundColor Yellow
        $allSubs.value | ForEach-Object { Write-Host "         - $($_.displayName) ($($_.subscriptionId)) [$($_.state)]" }
    }
} catch {
    Write-Host "  [FAIL] Azure OAuth Login Failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 3. Snowflake
Write-Host "`n[3/3] Snowflake Cloud Health:" -ForegroundColor Yellow
foreach ($k in @('SNOWFLAKE_ACCOUNT_PRIMARY', 'SNOWFLAKE_ACCOUNT_SECONDARY')) {
    $acct = $cfg[$k]
    $label = if ($k -match 'PRIMARY') { 'Primary (AWS)' } else { 'Secondary (Azure)' }
    if (-not $acct) {
        Write-Host "  [SKIP] $label: Account identifier not configured." -ForegroundColor Gray
        continue
    }

    $loginUser = if ($k -match 'SECONDARY' -and $cfg['SNOWFLAKE_SECONDARY_USER']) { $cfg['SNOWFLAKE_SECONDARY_USER'] } else { $cfg['SNOWFLAKE_USER'] }
    $loginPass = if ($k -match 'SECONDARY' -and $cfg['SNOWFLAKE_SECONDARY_PASSWORD']) { $cfg['SNOWFLAKE_SECONDARY_PASSWORD'] } else { $cfg['SNOWFLAKE_PASSWORD'] }

    try {
        $body = @{
            data = @{
                ACCOUNT_NAME       = $acct
                LOGIN_NAME         = $loginUser
                PASSWORD           = $loginPass
                CLIENT_APP_ID      = 'PythonConnector'
                CLIENT_APP_VERSION = '3.0.0'
            }
        } | ConvertTo-Json -Depth 4

        $url = "https://$($acct.ToLower()).snowflakecomputing.com/session/v1/login-request?roleName=$($cfg['SNOWFLAKE_ROLE'])"
        $r = Invoke-RestMethod -Method Post -Uri $url -ContentType 'application/json' -Body $body -TimeoutSec 15
        if ($r.success) {
            Write-Host "  [OK] Snowflake $label ($acct): Authentication Successful!" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] Snowflake $label ($acct): $($r.message) (Code: $($r.code))" -ForegroundColor Red
        }
    } catch {
        Write-Host "  [FAIL] Snowflake $label ($acct): Endpoint error: $($_.Exception.Message)" -ForegroundColor Red
    }
}
Write-Host "`n==========================================" -ForegroundColor Cyan
