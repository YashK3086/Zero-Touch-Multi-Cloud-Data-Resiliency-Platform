@echo off
setlocal
echo ======================================================================
echo [EMERGENCY CONTROL PLANE LAUNCHER] Multi-Cloud Snowflake DR Engine
echo ======================================================================

cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0emergency.ps1"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Launch failed. Please inspect terminal output.
    pause
)

