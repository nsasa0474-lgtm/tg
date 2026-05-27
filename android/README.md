# TGonPC для Android (APK)

Нативное приложение (`android-app/`): кнопка **«Запустить обход»** → тот же мост, что и `tgonpc.exe` на ПК (SOCKS5 `127.0.0.1:1080` → WebSocket MTProto / MTProxy).

В репозитории **нет** Android SDK и готового APK — собирайте локально.

---

## Требования

- **JDK 17** (или 11+)
- **Android SDK** (через Android Studio или command-line tools)
- Переменные: `ANDROID_HOME` или `ANDROID_SDK_ROOT`
- Windows: PowerShell; для buildozer/Kivy — Linux/WSL

SDK в git не входит (см. корневой `README.md`).

---

## Сборка APK (Gradle, рекомендуется)

Из корня репозитория:

```powershell
git clone https://github.com/nsasa0474-lgtm/tg.git
cd tg

# Скопировать Python-модуль в android-app
.\scripts\sync-python-src.ps1

cd android-app
.\gradlew.bat assembleDebug
```

APK: `android-app\app\build\outputs\apk\debug\app-debug.apk`

Или скрипт:

```powershell
.\scripts\build-apk-native.ps1
```

→ `dist\tgonpc-android-debug.apk`

---

## Сборка через Buildozer (Kivy, Linux/WSL)

```bash
pip install buildozer cython
buildozer android debug
```

APK: `bin/tgonpc-*-debug.apk`

---

## Установка и запуск

1. Установить APK на телефон.
2. **Запустить обход** — дождаться ✓ в статусе.
3. **Настроить Telegram** → «Подключить» (SOCKS5 `127.0.0.1:1080`).
4. Разрешить уведомления и отключить оптимизацию батареи для TGonPC (иначе Android может остановить обход).

Пока обход работает, не убивайте приложение — держите уведомление TGonPC активным.

---

## Пакет приложения

`applicationId`: `org.tgonpc.app`
