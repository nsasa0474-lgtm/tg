@echo off
cd /d "%~dp0.."
if exist "dist\tgonpc.exe" (
  start "" "dist\tgonpc.exe" --lan --no-browser
) else (
  python run.py --lan --no-browser
)
