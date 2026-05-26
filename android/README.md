# TG Tunnel для Android (APK)

Отдельное приложение: кнопка **«Запустить туннель»** → внутри тот же мост (SOCKS5 `127.0.0.1:1080` → WebSocket MTProto), что и `TGTunnel.exe` на ПК.

## Что делает приложение

1. Запускает локальный SOCKS5 на телефоне.
2. Кнопка **«Настроить Telegram»** открывает `tg://socks?...` — в Telegram нажмите **«Подключить»**.
3. Прокси остаётся в Telegram, пока включён туннель в приложении.

**Важно:** пока туннель работает, не закрывайте приложение насовсем (Android может убить фоновые процессы). Держите TG Tunnel в фоне или включите для него «без ограничений батареи».

---

## Сборка APK (нужен Linux или WSL)

На Windows APK собирают через **WSL2 (Ubuntu)** или Linux. На самом телефоне собрать нельзя.

### 1. WSL (Ubuntu)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake libffi-dev libssl-dev
pip install buildozer cython
```

### 2. Клон / копия проекта в WSL

```bash
cd /mnt/d/TG   # или скопируйте папку в ~/TG
```

### 3. Сборка

```bash
buildozer android debug
```

Готовый файл:

```text
bin/tgtunnel-1.0.0-arm64-v8a_armeabi-v7a-debug.apk
```

Скопируйте APK на телефон и установите (разрешите установку из неизвестных источников).

Первая сборка скачивает Android SDK/NDK (~2–4 ГБ, 30–60 минут).

### 4. Установка на телефон

- Перенесите APK (USB, Telegram «Избранное», облако).
- Откройте файл → Установить.
- При первом запуске: **Запустить туннель** → **Настроить Telegram** → **Подключить**.

---

## Если relay перестанет работать

Как на ПК: смените IP relay в коде (`DEFAULT_RELAY_IP` в `tg_bridge/config.py`) и пересоберите APK.

---

## Ограничения v1

- Нет отдельного «системного VPN» — только SOCKS5 в настройках Telegram (как на ПК).
- Нет Google Play — только свой APK (debug/release).
- Сборка только на Linux/WSL, не в Android Studio на Windows без WSL.
