@echo off
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Chua khoi tao moi truong ao .venv! Vui long xem README.md
    pause
    exit /b
)

".venv\Scripts\python.exe" main.py %*
pause
