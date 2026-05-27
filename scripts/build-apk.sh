#!/usr/bin/env bash
# Сборка APK в WSL/Linux из корня репозитория
set -euo pipefail
cd "$(dirname "$0")/.."
command -v buildozer >/dev/null || { echo "Установите: pip install buildozer"; exit 1; }
buildozer android debug
echo ""
echo "APK: bin/TGonPC-*-debug.apk"
