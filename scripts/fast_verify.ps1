$envFile = 'C:\CSPM_PROJECT\.env'
$cfg = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') {
        $cfg[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}

Write-Host "=== 1. AWS ===" -ForegroundColor Cyan
$env:AWS_ACCESS_KEY_ID = $cfg['AWS_ACCESS_KEY_ID']
$env:AWS_SECRET_ACCESS_KEY = $cfg['AWS_SECRET_ACCESS_KEY']
$env:AWS_DEFAULT_REGION = $cfg['AWS_REGION']
$awsId = aws sts get-caller-identity --output json 2>&1
if ($LASTEXITCODE -eq 0) {
    $j = $awsId | ConvertFrom-Json
    Write-Host "[OK] AWS Authenticated: Account $($j.Account)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] AWS STS error" -ForegroundColor Red
}

Write-Host "`n=== 2. AZURE ===" -ForegroundColor Cyan
$tenant = $cfg['AZURE_TENANT_ID']
$clientId = $cfg['AZURE_CLIENT_ID']
$clientSecret = $cfg['AZURE_CLIENT_SECRET']
$subId = $cfg['AZURE_SUBSCRIPTION_ID']

$tokenJson = curl.exe -s -X POST "https://login.microsoftonline.com/$tenant/oauth2/v2.0/token" `
  -d "client_id=$clientId" `
  -d "client_secret=$clientSecret" `
  -d "scope=https://management.azure.com/.default" `
  -d "grant_type=client_credentials"

$tokenObj = $tokenJson | ConvertFrom-Json
if ($tokenObj.access_token) {
    Write-Host "[OK] Azure OAuth Token obtained!" -ForegroundColor Green
    $bearer = "Authorization: Bearer $($tokenObj.access_token)"
    $subJson = curl.exe -s -H $bearer "https://management.azure.com/subscriptions/$subId`?api-version=2022-12-01"
    $subObj = $subJson | ConvertFrom-Json
    if ($subObj.displayName) {
        Write-Host "[OK] Azure Subscription: $($subObj.displayName) ($($subObj.state))" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Azure Subscription error: $subJson" -ForegroundColor Red
    }
} else {
    Write-Host "[FAIL] Azure OAuth failed: $tokenJson" -ForegroundColor Red
}

Write-Host "`n=== 3. SNOWFLAKE ===" -ForegroundColor Cyan
$acctPrimary = $cfg['SNOWFLAKE_ACCOUNT_PRIMARY']
$acctSecondary = $cfg['SNOWFLAKE_ACCOUNT_SECONDARY']

foreach ($acct in @($acctPrimary, $acctSecondary)) {
    if (-not $acct) { continue }
    $loginBody = @{
        data = @{
            ACCOUNT_NAME       = $acct
            LOGIN_NAME         = $cfg['SNOWFLAKE_USER']
            PASSWORD           = $cfg['SNOWFLAKE_PASSWORD']
            CLIENT_APP_ID      = 'PythonConnector'
            CLIENT_APP_VERSION = '3.0.0'
        }
    } | ConvertTo-Json -Depth 4

    $sfJson = curl.exe -s -X POST "https://$($acct.ToLower()).snowflakecomputing.com/session/v1/login-request?roleName=$($cfg['SNOWFLAKE_ROLE'])" `
      -H "Content-Type: application/json" `
      -d $loginBody

    $sfObj = $sfJson | ConvertFrom-Json
    if ($sfObj.success) {
        Write-Host "[OK] Snowflake ($acct): Authenticated!" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Snowflake ($acct): $($sfObj.message) (Code: $($sfObj.code))" -ForegroundColor Red
    }
}
