# Установка зависимостей tg_dpi
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Установка tg_dpi..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host ""
python -m tg_dpi check
Write-Host ""
Write-Host "Готово. Запуск (от администратора):" -ForegroundColor Green
Write-Host "  python -m tg_dpi start --strategy combo"
