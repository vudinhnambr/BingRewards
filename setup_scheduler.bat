@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: Check for administrative permissions
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Yeu cau quyen Administrator de dang ky Windows Task Scheduler...
    powershell -NoProfile -Command "Start-Process cmd -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)

echo Dang cai dat Windows Task Scheduler...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1"
pause
