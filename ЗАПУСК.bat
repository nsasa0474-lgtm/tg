@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TGonPC

if exist "dist\tgonpc.exe" (
    echo Запуск tgonpc.exe ...
    start "" "dist\tgonpc.exe"
    exit /b 0
)

if not exist "venv\Scripts\python.exe" (
    echo.
    echo Сначала один раз запустите: УСТАНОВИТЬ.bat
    echo.
    pause
    exit /b 1
)

echo Запуск TGonPC (нужны права администратора для Telegram)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\run-pc-admin.ps1"
