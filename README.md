# TGonPC (tgonpc)

Обход блокировок **Telegram на Windows (ПК)**. Программа поднимает локальный SOCKS5 `127.0.0.1:1080`, через него ходит **только приложение Telegram Desktop**.

Репозиторий: [github.com/nsasa0474-lgtm/tg](https://github.com/nsasa0474-lgtm/tg)

---

## Важно: что работает, а что нет

| Платформа / клиент | Статус |
|--------------------|--------|
| **Windows + Telegram Desktop** (программа с сайта telegram.org) | **Работает** — основной сценарий |
| **web.telegram.org** в браузере (Chrome, Edge и т.д.) | **Не работает** — не используйте |
| **Приложение TGonPC на Android** (`android-app/`, APK) | **Не работает** — заготовка в репозитории, автор не довёл до рабочего состояния |
| **Kivy / buildozer** (`mobile_app/`) | **Не работает** — то же самое, только черновик |

Если нужен Telegram **на телефоне** — этот проект вам **не поможет** (пока кто-то сам не доработает Android-часть). Можно попробовать подключить **официальный** Telegram на телефоне к SOCKS5 на вашем ПК в одной Wi‑Fi (`--lan`) — это отдельный трюк, без гарантий; см. ниже.

---

## Запуск для новичка (Windows)

Нужно: **Windows 10/11**, интернет, **Telegram Desktop** (не веб-версия в браузере).

### 1. Скачать проект

1. [github.com/nsasa0474-lgtm/tg](https://github.com/nsasa0474-lgtm/tg) → **Code** → **Download ZIP**
2. Распакуйте, например в `C:\tg`  
   Должны быть файлы `ЗАПУСК.bat`, `УСТАНОВИТЬ.bat`, `run.py`.

### 2. Установить Python (один раз)

1. [python.org/downloads](https://www.python.org/downloads/) → Python **3.11** или **3.12**
2. В установщике включить: **`Add python.exe to PATH`**
3. Проверка: `Win + R` → `cmd` → `python --version`

### 3. Установить TGonPC (один раз)

Дважды щёлкните **`УСТАНОВИТЬ.bat`** → дождитесь **«Готово!»**

### 4. Запустить

Дважды щёлкните **`ЗАПУСК.bat`**:

1. UAC → **Да**
2. Чёрное окно **не закрывать**
3. Откроется или запустите **Telegram Desktop** (не сайт web.telegram.org)
4. Нажмите **«Подключить»**, если спросит прокси

**Остановка:** закрыть окно или `Ctrl + C`.

### 5. Прокси вручную в Telegram Desktop

**Настройки** → **Данные и память** → **Тип прокси** → SOCKS5:

- Сервер: `127.0.0.1` (не `localhost`)
- Порт: `1080`
- Логин/пароль: пусто

---

## Частые проблемы

| Симптом | Что сделать |
|--------|-------------|
| Открыли web.telegram.org | **Не поддерживается.** Установите **Telegram Desktop** |
| Хотите APK на телефон | **Не готово.** См. `android/README.md` — только для самостоятельной доработки |
| «Python не найден» | Python с галочкой PATH → снова `УСТАНОВИТЬ.bat` |
| Telegram не коннектится | SOCKS5 `127.0.0.1:1080`, окно TGonPC открыто |
| «Запрет» + YouTube | Сначала Запрет, потом `scripts\run-zapret-friendly.bat` |

Лог: `logs\tgonpc.log`

---

## Запуск из PowerShell

```powershell
cd C:\tg
.\venv\Scripts\python.exe run.py
```

Или `.\scripts\run-pc-admin.ps1`. Флаг `--browser` открывает web.telegram.org — **обычно бесполезен**.

---

## Один файл .exe

```powershell
pip install -r requirements-build.txt
python build.py
```

→ `dist\tgonpc.exe` — только **Telegram Desktop**, не браузер.

---

## Телефон через Wi‑Fi и ПК (без APK TGonPC)

Иногда помогает **официальный** Telegram на телефоне, если ПК в той же сети:

1. На ПК: `python run.py --lan` (окно не закрывать)
2. `ipconfig` → IPv4 ПК, например `192.168.1.50`
3. В Telegram **на телефоне**: SOCKS5 `192.168.1.50:1080`

Это **не** наше Android-приложение; на LTE без ПК так не заработает.

---

## Android / мобильная версия (не работает)

Каталоги `android-app/`, `mobile_app/`, `android/` — **эксперимент**, в текущем виде **не запускается нормально**.

Хотите починить — читайте **`android/README.md`**, собирайте сами, правьте код. Готового APK в репозитории нет.

---

## Модули (ПК)

- **`tg_bridge`** — основной обход (SOCKS5 → WebSocket).
- **`tg_dpi`** — опционально, WinDivert, нужен админ.

---

## Совместимость с «Запрет»

`scripts\run-zapret-friendly.bat` или `tgonpc.exe --zapret` — после запуска Запрета.

---

## Структура

```text
ЗАПУСК.bat / УСТАНОВИТЬ.bat   — запуск на Windows (рабочее)
run.py / tg_bridge/            — мост для Desktop Telegram
android-app/ / mobile_app/     — НЕ РАБОТАЕТ, для доработки
```

## Лицензия

MIT.
