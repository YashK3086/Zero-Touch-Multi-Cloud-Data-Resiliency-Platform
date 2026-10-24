<#
.SYNOPSIS
  Loads ../.env into the current PowerShell session and maps values to the
  environment variables expected by Terraform providers and the DR controller.
.USAGE
  . .\scripts\Load-Env.ps1          # dot-source so variables persist in your session
  . .\scripts\Load-Env.ps1 -Quiet
#>
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\.env'),
    [switch]$Quiet
)

if (-not (Test-Path $EnvFile)) { throw ".env not found at $EnvFile" }

$cfg = @{}
foreach ($line in Get-Content $EnvFile) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line -split '=', 2
    $cfg[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
}

# 1) Export every key as-is (used by the Python controller)
foreach ($k in $cfg.Keys) { Set-Item -Path "Env:$k" -Value $cfg[$k] }

# 2) Provider-specific mappings
$map = [ordered]@{
    'ARM_SUBSCRIPTION_ID'                   = 'AZURE_SUBSCRIPTION_ID'
    'ARM_TENANT_ID'                         = 'AZURE_TENANT_ID'
    'ARM_CLIENT_ID'                         = 'AZURE_CLIENT_ID'
    'ARM_CLIENT_SECRET'                     = 'AZURE_CLIENT_SECRET'
    'AWS_DEFAULT_REGION'                    = 'AWS_REGION'
    'TF_VAR_snowflake_user'                 = 'SNOWFLAKE_USER'
    'TF_VAR_snowflake_role'                 = 'SNOWFLAKE_ROLE'
    'TF_VAR_snowflake_primary_account'      = 'SNOWFLAKE_ACCOUNT_PRIMARY'
    'TF_VAR_snowflake_secondary_account'    = 'SNOWFLAKE_ACCOUNT_SECONDARY'
    'TF_VAR_snowflake_private_key_path'     = 'SNOWFLAKE_PRIVATE_KEY_PATH'
}
if (-not $cfg.ContainsKey('SNOWFLAKE_PRIVATE_KEY_PATH') -or $cfg['SNOWFLAKE_PRIVATE_KEY_PATH'] -eq '') {
    $map['TF_VAR_snowflake_password'] = 'SNOWFLAKE_PASSWORD'
} else {
    Remove-Item Env:TF_VAR_snowflake_password -ErrorAction SilentlyContinue
    Remove-Item Env:SNOWFLAKE_PASSWORD -ErrorAction SilentlyContinue
}
foreach ($target in $map.Keys) {
    $src = $map[$target]
    if ($cfg.ContainsKey($src) -and $cfg[$src] -ne '') { Set-Item -Path "Env:$target" -Value $cfg[$src] }
}

if (-not $Quiet) {
    Write-Host "Loaded $($cfg.Count) keys from .env (values hidden):" -ForegroundColor Cyan
    $cfg.Keys | Sort-Object | ForEach-Object { Write-Host "  $_" }
}
