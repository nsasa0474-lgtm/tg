@echo off
cd /d "%~dp0.."
if exist "dist\TGTunnel.exe" (
  start "" "dist\TGTunnel.exe" --lan --no-browser
) else (
  python run.py --lan --no-browser
)
