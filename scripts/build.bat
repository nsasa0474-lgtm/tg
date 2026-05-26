@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo TG Tunnel - сборка одного EXE
echo.

if exist "venv\Scripts\python.exe" (
    set PY=venv\Scripts\python.exe
) else (
    set PY=python
)

"%PY%" build.py
if errorlevel 1 (
    echo.
    echo Ошибка сборки.
    pause
    exit /b 1
)

echo.
echo Файл: dist\TGTunnel.exe
pause
