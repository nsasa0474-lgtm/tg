from __future__ import annotations

import logging
import os
import subprocess
import sys

log = logging.getLogger("tg_bridge")

WEB_URL = "https://web.telegram.org"


def _browser_candidates() -> list[str]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pfx86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(pfx86, "Microsoft", "Edge", "Application", "msedge.exe"),
    ]


def open_web_telegram(host: str = "127.0.0.1", http_port: int = 1081) -> bool:
    """
    Запуск Chrome/Edge с --proxy-server (обходит игнор системного прокси).
    """
    proxy = f"http://{host}:{http_port}"
    args_base = [
        f"--proxy-server={proxy}",
        "--proxy-bypass-list=<-loopback>",
        WEB_URL,
    ]
    for exe in _browser_candidates():
        if not os.path.isfile(exe):
            continue
        try:
            subprocess.Popen(
                [exe, *args_base],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log.info("Браузер: %s (прокси %s)", os.path.basename(exe), proxy)
            return True
        except OSError as exc:
            log.warning("Не удалось запустить %s: %s", exe, exc)
    log.warning(
        "Chrome/Edge не найден — установите браузер или откройте %s вручную с прокси %s",
        WEB_URL,
        proxy,
    )
    return False
