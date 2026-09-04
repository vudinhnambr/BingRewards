@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Dang cai dat Windows Task Scheduler...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_scheduler.ps1"
pause
