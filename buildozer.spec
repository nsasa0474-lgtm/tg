[app]

title = TGonPC
package.name = tgonpc
package.domain = org.tgonpc
source.dir = .
source.include_exts = py,png,txt
source.include_patterns = tg_bridge/*,mobile_app/*
source.exclude_dirs = tests,bin,venv,.git,.idea,build,dist,tg_dpi,agent-transcripts
version = 1.0.0

requirements = python3,kivy,pyaes,pyjnius,hostpython3,setuptools

orientation = portrait
fullscreen = 0

icon.filename = mobile_app/icon.png

[buildozer]

log_level = 2
warn_on_root = 1

[android]

android.permissions = INTERNET,FOREGROUND_SERVICE,POST_NOTIFICATIONS,WAKE_LOCK
android.api = 33
android.minapi = 24
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.accept_sdk_license = True
android.release_artifact = apk
