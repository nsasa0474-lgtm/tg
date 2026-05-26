from __future__ import annotations

import atexit
import ctypes
import json
import logging
import os
import winreg
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar

log = logging.getLogger("tg_bridge")

INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
INTERNET_OPTION_SETTINGS_CHANGED = 39
INTERNET_OPTION_REFRESH = 37

_wininet = ctypes.windll.wininet

_BACKUP_FILE = Path(os.environ.get("TEMP", ".")) / "tg_tunnel_proxy_backup.json"


def _notify_proxy_change() -> None:
    _wininet.InternetSetOptionW(0, INTERNET_OPTION_SETTINGS_CHANGED, 0, 0)
    _wininet.InternetSetOptionW(0, INTERNET_OPTION_REFRESH, 0, 0)


@dataclass
class _SavedProxy:
    enable: int
    server: str
    override: str
    auto_config: str


def _write_backup(saved: _SavedProxy) -> None:
    try:
        _BACKUP_FILE.write_text(json.dumps(asdict(saved)), encoding="utf-8")
    except OSError:
        pass


def _restore_backup() -> bool:
    """Вернуть прокси из бэкапа (после сбоя), не обнулять настройки Запрета и др."""
    if not _BACKUP_FILE.is_file():
        return False
    try:
        data = json.loads(_BACKUP_FILE.read_text(encoding="utf-8"))
        saved = _SavedProxy(
            int(data["enable"]),
            str(data["server"]),
            str(data["override"]),
            str(data.get("auto_config", "")),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return False
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_ALL_ACCESS)
    try:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, saved.enable)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, saved.server)
        winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, saved.override)
        if saved.auto_config:
            winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, saved.auto_config)
        else:
            try:
                winreg.DeleteValue(key, "AutoConfigURL")
            except OSError:
                pass
    finally:
        winreg.CloseKey(key)
    _notify_proxy_change()
    try:
        _BACKUP_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    log.info("Восстановлен системный прокси из бэкапа")
    return True


def _is_ours(host: str, socks_port: int, http_port: int, pac_port: int) -> bool:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_READ)
    try:
        try:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            s = str(server)
            if (
                f"{host}:{socks_port}" in s
                or f"{host}:{http_port}" in s
                or f"socks={host}" in s
                or f"http={host}" in s
            ):
                return True
        except OSError:
            pass
        try:
            pac, _ = winreg.QueryValueEx(key, "AutoConfigURL")
            if f"{host}:{pac_port}" in str(pac):
                return True
        except OSError:
            pass
        return False
    finally:
        winreg.CloseKey(key)


def force_disable_ours(
    host: str = "127.0.0.1",
    socks_port: int = 1080,
    http_port: int = 1081,
    pac_port: int = 1082,
) -> None:
    """Убрать наш прокси; по возможности восстановить то, что было до TG Tunnel."""
    if not _is_ours(host, socks_port, http_port, pac_port):
        return
    if _restore_backup():
        return
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_ALL_ACCESS)
    try:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        try:
            winreg.DeleteValue(key, "AutoConfigURL")
        except OSError:
            pass
        log.info("Сброшен системный прокси Windows (остаток TG Tunnel)")
    finally:
        winreg.CloseKey(key)
    _notify_proxy_change()


class SystemProxy:
    """HTTP + SOCKS + PAC (Chrome/Edge подхватывают PAC и HTTP)."""

    _active: ClassVar[SystemProxy | None] = None

    def __init__(
        self,
        host: str = "127.0.0.1",
        socks_port: int = 1080,
        http_port: int = 1081,
        pac_port: int = 1082,
    ) -> None:
        self.host = host
        self.socks_port = socks_port
        self.http_port = http_port
        self.pac_port = pac_port
        self._saved: _SavedProxy | None = None

    @property
    def proxy_server(self) -> str:
        return f"http={self.host}:{self.http_port};socks={self.host}:{self.socks_port}"

    @property
    def pac_url(self) -> str:
        return f"http://{self.host}:{self.pac_port}/proxy.pac"

    def enable(self) -> None:
        if SystemProxy._active is not None:
            return
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_ALL_ACCESS)
        try:
            try:
                enable, _ = winreg.QueryValueEx(key, "ProxyEnable")
            except OSError:
                enable = 0
            try:
                server, _ = winreg.QueryValueEx(key, "ProxyServer")
            except OSError:
                server = ""
            try:
                override, _ = winreg.QueryValueEx(key, "ProxyOverride")
            except OSError:
                override = "<local>"
            try:
                auto_config, _ = winreg.QueryValueEx(key, "AutoConfigURL")
            except OSError:
                auto_config = ""

            self._saved = _SavedProxy(int(enable), str(server), str(override), str(auto_config))
            _write_backup(self._saved)

            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, self.proxy_server)
            winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, self.pac_url)
            winreg.SetValueEx(
                key,
                "ProxyOverride",
                0,
                winreg.REG_SZ,
                "<local>;127.*;10.*;172.16.*;172.17.*;172.18.*;172.19.*;"
                "172.20.*;172.21.*;172.22.*;172.23.*;172.24.*;172.25.*;"
                "172.26.*;172.27.*;172.28.*;172.29.*;172.30.*;172.31.*;192.168.*",
            )
        finally:
            winreg.CloseKey(key)

        _notify_proxy_change()
        SystemProxy._active = self
        atexit.register(self.disable)
        log.info("Системный прокси: %s", self.proxy_server)
        log.info("PAC: %s", self.pac_url)

    def disable(self) -> None:
        if SystemProxy._active is not None and SystemProxy._active is not self:
            SystemProxy._active.disable()
        if self._saved is None:
            return
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_ALL_ACCESS)
        try:
            winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, self._saved.enable)
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, self._saved.server)
            winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, self._saved.override)
            if self._saved.auto_config:
                winreg.SetValueEx(key, "AutoConfigURL", 0, winreg.REG_SZ, self._saved.auto_config)
            else:
                try:
                    winreg.DeleteValue(key, "AutoConfigURL")
                except OSError:
                    pass
        finally:
            winreg.CloseKey(key)
        _notify_proxy_change()
        self._saved = None
        if SystemProxy._active is self:
            SystemProxy._active = None
        try:
            _BACKUP_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        log.info("Системный прокси восстановлен")

    def __enter__(self) -> SystemProxy:
        self.enable()
        return self

    def __exit__(self, *_) -> None:
        self.disable()
