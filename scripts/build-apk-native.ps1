# Сборка debug APK на Windows (Gradle + Chaquopy)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root = Split-Path $PSScriptRoot -Parent
$Tools = Join-Path $Root ".tools"
$SdkRoot = Join-Path $Root ".android-sdk"
$GradleHome = Join-Path $Tools "gradle-8.14"
$GradleZip = Join-Path $Tools "gradle-8.14-bin.zip"
$Py312 = Join-Path $Tools "python312"
$Py312Exe = Join-Path $Py312 "python.exe"
$CmdlineZip = Join-Path $Tools "commandlinetools-win.zip"
$CmdlineDir = Join-Path $SdkRoot "cmdline-tools\latest"

function Ensure-Dir($p) { New-Item -ItemType Directory -Force -Path $p | Out-Null }

Write-Host "== TG Tunnel: build APK ==" -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "sync-python-src.ps1")

Ensure-Dir $Tools
Ensure-Dir $SdkRoot

if (-not (Test-Path (Join-Path $Py312 "Lib\encodings"))) {
    Write-Host "Downloading Python 3.12 standalone..."
    if (Test-Path $Py312) { Remove-Item -Recurse -Force $Py312 }
    $pyTar = Join-Path $Tools "cpython-3.12.7-win64.tar.gz"
    if (-not (Test-Path $pyTar)) {
        Invoke-WebRequest -Uri "https://github.com/astral-sh/python-build-standalone/releases/download/20241016/cpython-3.12.7%2B20241016-x86_64-pc-windows-msvc-shared-install_only.tar.gz" -OutFile $pyTar
    }
    tar -xzf $pyTar -C $Tools
    $extracted = Get-ChildItem $Tools -Directory | Where-Object { $_.Name -like "python*" -and $_.Name -ne "python312" } | Select-Object -First 1
    if ($extracted) { Move-Item $extracted.FullName $Py312 -Force }
    if (-not (Test-Path (Join-Path $Py312 "python.exe"))) {
        $inner = Get-ChildItem $Py312 -Recurse -Filter "python.exe" | Select-Object -First 1
        if ($inner) { Copy-Item $inner.Directory.Parent.FullName\* $Py312 -Recurse -Force -ErrorAction SilentlyContinue }
    }
    if (-not (Test-Path $Py312Exe)) { throw "Python 3.12 unpack failed" }
    $oldEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Py312Exe -m ensurepip --upgrade 2>&1 | Out-Null
    $ErrorActionPreference = $oldEap
}

if (-not (Test-Path (Join-Path $GradleHome "bin\gradle.bat"))) {
    Write-Host "Downloading Gradle 8.14..."
    Invoke-WebRequest -Uri "https://services.gradle.org/distributions/gradle-8.14-bin.zip" -OutFile $GradleZip
    Expand-Archive -Path $GradleZip -DestinationPath $Tools -Force
}

if (-not (Test-Path (Join-Path $CmdlineDir "bin\sdkmanager.bat"))) {
    Write-Host "Downloading Android commandlinetools..."
    Invoke-WebRequest -Uri "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip" -OutFile $CmdlineZip
    Ensure-Dir (Join-Path $SdkRoot "cmdline-tools")
    Expand-Archive -Path $CmdlineZip -DestinationPath (Join-Path $SdkRoot "cmdline-tools\_tmp") -Force
    $inner = Get-ChildItem (Join-Path $SdkRoot "cmdline-tools\_tmp") | Select-Object -First 1
    Ensure-Dir (Split-Path $CmdlineDir)
    Move-Item $inner.FullName $CmdlineDir -Force
    Remove-Item -Recurse -Force (Join-Path $SdkRoot "cmdline-tools\_tmp") -ErrorAction SilentlyContinue
}

$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot
$sdkmanager = Join-Path $CmdlineDir "bin\sdkmanager.bat"

Write-Host "Installing Android SDK (first run is slow)..."
$yes = "y`n" * 20
$yes | & $sdkmanager --sdk_root=$SdkRoot "platform-tools" "platforms;android-34" "build-tools;34.0.0" "ndk;26.1.10909125" 2>&1 | Out-Host

$javaHome = "C:\Program Files\Java\jdk-24"
if (Test-Path $javaHome) { $env:JAVA_HOME = $javaHome }

$env:TG_BUILD_PYTHON = $Py312Exe.Replace('\', '/')

$gradle = Join-Path $GradleHome "bin\gradle.bat"
Push-Location (Join-Path $Root "android-app")
try {
    Write-Host "Gradle assembleDebug (Python 3.12 for Chaquopy)..."
    $max = 3
    for ($i = 1; $i -le $max; $i++) {
        & $gradle assembleDebug --no-daemon --stacktrace "-PbuildPython=$env:TG_BUILD_PYTHON"
        if ($LASTEXITCODE -eq 0) { break }
        if ($i -lt $max) {
            Write-Host "Retry $i/$max after pip timeout..."
            Start-Sleep -Seconds 5
        } else {
            throw "Gradle failed after $max attempts"
        }
    }
} finally {
    Pop-Location
}

$apk = Get-ChildItem -Path (Join-Path $Root "android-app\app\build\outputs\apk\debug") -Filter "*.apk" | Select-Object -First 1
if (-not $apk) { throw "APK not found after build" }

Ensure-Dir (Join-Path $Root "dist")
$out = Join-Path $Root "dist\TGTunnel-android-debug.apk"
Copy-Item $apk.FullName $out -Force
Write-Host ""
Write-Host "DONE: $out" -ForegroundColor Green
Write-Host "Size MB: $([math]::Round((Get-Item $out).Length/1MB, 1))"
