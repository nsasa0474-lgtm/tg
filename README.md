# TGonPC (tgonpc)

Локальный обход блокировок Telegram на ПК и Android: SOCKS5 `127.0.0.1:1080` → MTProto через WebSocket (HTTPS) или MTProxy. Это **не VPN-туннель** — трафик идёт только в Telegram, системный прокси по умолчанию не трогаем.

Репозиторий: [github.com/nsasa0474-lgtm/tg](https://github.com/nsasa0474-lgtm/tg)

---

## Что в репозитории, а что нет

В git только **исходники** (~150 файлов). Не залиты (ставятся локально):

| Папка / файл | Зачем |
|--------------|--------|
| `venv/` | Python-зависимости |
| `.tools/` | встроенный Python для скриптов (опционально) |
| `.android-sdk/` | SDK для сборки APK |
| `dist/`, `build/` | `tgonpc.exe` и артефакты сборки |
| `logs/` | логи запуска |

---

## Быстрый старт после клонирования (Windows)

```powershell
git clone https://github.com/nsasa0474-lgtm/tg.git
cd tg

python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

python run.py
```

При запросе UAC нажмите **Да** (нужно для автонастройки Telegram). В Telegram — **«Подключить»** (SOCKS5 `127.0.0.1:1080`).

Альтернатива с правами админа:

```powershell
.\scripts\run-pc-admin.ps1
```

Остановка: `Ctrl+C` — системный прокси Windows (если включали) восстанавливается.

### Проверка без UAC

```powershell
python run.py --no-uac
```

В Telegram включите прокси вручную: SOCKS5 `127.0.0.1:1080`.

---

## Модули

**`tg_bridge`** — основной обход: SOCKS5 → WebSocket на `kws*.web.telegram.org` через relay `149.154.167.220`.

**`tg_dpi`** (WinDivert) — только если TCP до DC доступен (`python -m tg_dpi probe` → OK). При полной блокировке IP не поможет.

```powershell
pip install -r requirements.txt
python -m tg_dpi check
python -m tg_dpi start --strategy combo
```

Нужны права администратора.

---

## Сборка одного EXE (на своей машине)

```powershell
pip install -r requirements-build.txt
python build.py
```

или `scripts\build.bat` → **`dist\tgonpc.exe`** (~13 MB). На другом ПК: скопировать и запустить, Python не нужен.

```text
tgonpc.exe --no-browser
tgonpc.exe --no-tg-link
tgonpc.exe --lan
tgonpc.exe -v
tgonpc.exe --system-proxy
tgonpc.exe --zapret
```

Готовый exe в репозитории **не хранится** — соберите сами.

---

## Режим `pc` (по умолчанию)

1. **SOCKS5** `127.0.0.1:1080` — только для Telegram (`tg://socks`).
2. **Системный прокси Windows выключен** — не ломает «Запрет», YouTube, Discord.
3. Прокси на весь ПК: `tgonpc.exe --system-proxy` или `python run.py --system-proxy`.
4. **NAT** (`--nat`) — редко, может конфликтовать с WinDivert у «Запрета».

### Telegram на телефоне в Wi‑Fi

1. На ПК: `tgonpc.exe --lan` или `python run.py --lan`.
2. IP ПК: `ipconfig` → IPv4, например `192.168.1.50`.
3. Телефон в той же Wi‑Fi.
4. Telegram → Прокси → SOCKS5 → `192.168.1.50:1080`.

ПК должен быть включён, TGonPC запущен. Через 4G без ПК не работает.

### Termux на Android

[Termux](https://termux.org) → `pkg install python`, скопировать проект, `pip install -r requirements.txt`, `python run.py` → SOCKS5 `127.0.0.1:1080`.

### APK (отдельное приложение)

Сборка и установка: **`android/README.md`**. На телефоне: **Запустить обход** → **Настроить Telegram** → «Подключить».

---

## Совместимость с «Запрет»

```powershell
.\scripts\run-zapret-friendly.bat
```

или `tgonpc.exe --zapret`

Порядок: сначала **Запрет**, потом **TGonPC**. В Telegram — SOCKS `127.0.0.1:1080`.

---

## CLI

```powershell
python -m tg_bridge --port 1080 -v
python -m tg_bridge --relay-ip 149.154.167.220
```

---

## Структура

```text
tg_bridge/     — SOCKS5 → WebSocket (основной обход)
tg_dpi/        — обход DPI пакетами (если IP не заблокирован)
run.py         — запуск на ПК
android-app/   — нативное Android-приложение (Gradle)
mobile_app/    — Kivy-оболочка (buildozer)
scripts/       — run, сборка, sync
```

## Лицензия

MIT. Идеи протокола: публичные описания MTProto/WebSocket relay.
