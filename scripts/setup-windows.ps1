# Первая установка TGonPC на Windows (один раз)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TGonPC — установка зависимостей" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Python {
    try {
        $v = & python --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $v -match "Python 3") { return $true }
    } catch {}
    return $false
}

if (-not (Test-Python)) {
    Write-Host "Python 3 не найден." -ForegroundColor Red
    Write-Host ""
    Write-Host "1) Скачайте установщик: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "2) При установке включите галочку:" -ForegroundColor Yellow
    Write-Host "   [x] Add python.exe to PATH" -ForegroundColor Yellow
    Write-Host "3) Закройте это окно, откройте снова и запустите УСТАНОВИТЬ.bat" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Нажмите Enter для выхода"
    exit 1
}

Write-Host "Python: $(python --version)" -ForegroundColor Green

$venvPy = Join-Path $Root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Создаю виртуальное окружение venv ..." -ForegroundColor Cyan
    python -m venv venv
    if (-not (Test-Path $venvPy)) {
        Write-Host "Не удалось создать venv." -ForegroundColor Red
        Read-Host "Enter"
        exit 1
    }
}

Write-Host "Устанавливаю пакеты (1–2 минуты) ..." -ForegroundColor Cyan
& $venvPy -m pip install -q -U pip
& $venvPy -m pip install -q -r (Join-Path $Root "requirements.txt")

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Готово!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Дальше: закройте это окно и дважды щёлкните" -ForegroundColor White
Write-Host "  ЗАПУСК.bat" -ForegroundColor Yellow
Write-Host ""
Write-Host "В Telegram нажмите «Подключить», если спросит прокси." -ForegroundColor White
Write-Host ""
Read-Host "Нажмите Enter"
