# Копирует tg_bridge в android-app для Chaquopy
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$dst = Join-Path $root "android-app\app\src\main\python\tg_bridge"
$src = Join-Path $root "tg_bridge"
if (-not (Test-Path $src)) { throw "tg_bridge not found: $src" }
New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null
if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
Copy-Item -Recurse $src $dst
Write-Host "OK: $dst"
