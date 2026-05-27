@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if exist "dist\tgonpc.exe" (
    start "" "dist\tgonpc.exe"
    exit /b 0
)

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run.py
) else (
    python run.py
)
