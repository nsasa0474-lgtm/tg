# Android / телефон — не работает

> **На телефоне TGonPC сейчас не работает.**  
> Рабочий вариант — **Windows** + **Telegram Desktop** + `ЗАПУСК.bat` (корневой `README.md`).

Исходники Android-части лежат в репозитории — можно форкнуть и доработать. Ниже — как собрать черновик, **без гарантии**, что заработает.

---

## Что в репозитории

| Папка | Описание |
|-------|----------|
| `android-app/` | Gradle + Chaquopy, `org.tgonpc.app` |
| `mobile_app/` | Kivy + buildozer |
| `buildozer.spec` | Сборка APK (Linux/WSL) |

Готового APK на GitHub нет. Android SDK в git не входит.

---

## Сборка (на свой риск)

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

## Почему на Android не взлетело

- Нужны foreground service, сетевые callback, стабильный MTProxy — в этой сборке **нестабильно**.
- На LTE у многих операторов обход с телефона **не поднимается** так же, как с ПК.
- Сейчас **фокус на Windows**; Android — не приоритет.

---

## Если будете дорабатывать

1. Форк репозитория.
2. Правки в `android-app/`, `tg_bridge` (`android_java`, `relay_pool`, `TgonpcService`).
3. Тест на устройстве: Wi‑Fi и LTE отдельно.

Пакет: `org.tgonpc.app`

---

## Итого

| Вариант | Статус |
|---------|--------|
| Windows + Telegram Desktop | **Работает** |
| web.telegram.org | **Не работает** |
| APK TGonPC на Android | **Не работает** |
