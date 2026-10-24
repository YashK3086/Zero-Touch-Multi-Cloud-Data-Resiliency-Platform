$envFile = 'C:\CSPM_PROJECT\.env'
$cfg = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=\s]+)\s*=\s*(.*)$') {
        $cfg[$matches[1]] = $matches[2].Trim().Trim('"').Trim("'")
    }
}

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
$bearer = "Authorization: Bearer $($tokenObj.access_token)"

Write-Host "Registering Microsoft.Storage on subscription $subId..."
$reg = curl.exe -s -X POST -H $bearer -H "Content-Length: 0" "https://management.azure.com/subscriptions/$subId/providers/Microsoft.Storage/register?api-version=2021-04-01"
Write-Host $reg

Start-Sleep -Seconds 5
$status = curl.exe -s -H $bearer "https://management.azure.com/subscriptions/$subId/providers/Microsoft.Storage?api-version=2021-04-01"
$statusObj = $status | ConvertFrom-Json
Write-Host "Registration State: $($statusObj.registrationState)"
