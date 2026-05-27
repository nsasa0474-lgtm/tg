# Android / телефон — не работает

> **Статус: нерабочая заготовка.**  
> Сборка APK и запуск на телефоне **в текущем репозитории не доведены до результата**.  
> Если вам нужен рабочий Telegram на телефоне — **используйте Windows-версию** (`ЗАПУСК.bat` + **Telegram Desktop** на ПК), см. корневой `README.md`.

Код оставлен **как есть** — чтобы кто-то мог **сам доработать** (pull request, форк). Ниже — как собрать черновик, без обещания, что заработает.

---

## Что есть в репозитории

| Папка | Описание |
|-------|----------|
| `android-app/` | Gradle + Chaquopy, Java `org.tgonpc.app` |
| `mobile_app/` | Kivy-оболочка для buildozer |
| `buildozer.spec` | Сборка APK через buildozer (Linux/WSL) |

**Готового APK на GitHub нет.** Android SDK в git не входит.

---

## Для разработчика: сборка (на свой страх и риск)

### Gradle (Windows)

```powershell
cd tg
.\scripts\sync-python-src.ps1
cd android-app
.\gradlew.bat assembleDebug
```

APK: `android-app\app\build\outputs\apk\debug\app-debug.apk`

### Buildozer (Linux/WSL)

```bash
buildozer android debug
```

---

## Известные проблемы (почему «не получилось»)

- Обход на Android требует VPN/foreground service, сетевых callback и стабильного MTProxy — в текущей сборке это **нестабильно**.
- На многих операторах LTE обход с телефона **не поднимается** так же, как с ПК.
- Проект **не поддерживается** автором на Android; issue «не работает на телефоне» ожидаемы.

---

## Если дорабатываете

1. Форк репозитория.
2. Правки в `android-app/` и `tg_bridge/` (модули `android_java`, `relay_pool`, `TgonpcService`).
3. Тесты на реальном устройстве (Wi‑Fi и LTE отдельно).

Пакет: `org.tgonpc.app`

---

## ПК остаётся единственным поддерживаемым сценарием

**Telegram Desktop** на Windows + `ЗАПУСК.bat` / `tgonpc.exe`.  
**web.telegram.org** и **мобильное приложение TGonPC** — не рабочие варианты сейчас.
