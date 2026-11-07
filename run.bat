@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
)

"%PY_EXE%" main.py %*
pause
