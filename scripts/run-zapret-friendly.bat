@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
echo TGonPC + Zapret: только Telegram, без системного прокси
echo.
if exist "dist\tgonpc.exe" (
    "dist\tgonpc.exe" --zapret
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run.py --zapret
) else (
    python run.py --zapret
)
pause
