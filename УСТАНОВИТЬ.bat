@echo off
chcp 65001 >nul
cd /d "%~dp0"
title TGonPC — установка
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup-windows.ps1"
pause
