from __future__ import annotations

import logging
import os
import subprocess
import webbrowser

log = logging.getLogger("tg_bridge")


def apply_telegram_proxy(host: str = "127.0.0.1", port: int = 1080) -> None:
    """
    Официальный способ: tg:// ссылка — Telegram сам предложит включить SOCKS5.
    Один клик «Подключить», без ручного ввода host/port.
    """
    link = f"tg://socks?server={host}&port={port}"
    log.status("Открываем %s", link)
    if _open_telegram_proxy_android(link):
        return
    try:
        os.startfile(link)  # type: ignore[attr-defined]
    except (OSError, AttributeError):
        try:
            webbrowser.open(link)
        except Exception as exc:
            log.warning("Не удалось открыть tg:// ссылку: %s", exc)


def _open_telegram_proxy_android(link: str) -> bool:
    try:
        from jnius import autoclass

        Intent = autoclass("android.content.Intent")
        Uri = autoclass("android.net.Uri")
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        activity = PythonActivity.mActivity
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(link))
        activity.startActivity(intent)
        return True
    except Exception:
        return False


def find_telegram_exe() -> str | None:
    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Telegram Desktop\Telegram.exe"),
        os.path.expandvars(r"%APPDATA%\Telegram Desktop\Telegram.exe"),
        r"C:\Program Files\WindowsApps\TelegramMessengerLLP.TelegramDesktop_*\Telegram.exe",
    ]
    for path in candidates:
        if "*" not in path and os.path.isfile(path):
            return path
    return None
