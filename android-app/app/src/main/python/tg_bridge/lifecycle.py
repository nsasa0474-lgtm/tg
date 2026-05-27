from __future__ import annotations

import asyncio
import atexit
import logging
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tg_bridge.platform import is_android

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig
    from tg_bridge.system_proxy import SystemProxy

log = logging.getLogger("tg_bridge")

_STATE: RuntimeState | None = None


@dataclass
class RuntimeState:
    cfg: BridgeConfig
    system_proxy_enabled: bool = False
    use_nat: bool = False
    auto_tg: bool = True
    auto_browser: bool = False
    proxy_ctx: Any = None
    servers: list[asyncio.Server] = field(default_factory=list)
    tasks: list[asyncio.Task] = field(default_factory=list)


def bind_state(state: RuntimeState) -> None:
    global _STATE
    _STATE = state


def recover_stale_proxy(cfg: BridgeConfig) -> None:
    """Только если прошлый запуск TGonPC оставил СВОЙ прокси — не трогать Запрет."""
    if is_android():
        return
    try:
        from tg_bridge.system_proxy import force_disable_ours

        force_disable_ours(cfg.host, cfg.port, cfg.http_port, cfg.pac_port)
    except Exception:
        pass


async def async_shutdown(state: RuntimeState | None = None) -> None:
    """Остановить серверы и задачи (внутри asyncio)."""
    global _STATE
    if state is None:
        state = _STATE
    if state is None:
        return

    for task in list(state.tasks):
        if not task.done():
            task.cancel()
    if state.tasks:
        await asyncio.gather(*state.tasks, return_exceptions=True)

    for server in list(state.servers):
        server.close()
        await server.wait_closed()
    state.tasks.clear()
    state.servers.clear()

    if state.proxy_ctx is not None:
        try:
            state.proxy_ctx.disable()
        except Exception:
            pass
        state.proxy_ctx = None


def full_shutdown(cfg: BridgeConfig | None = None, *, quiet: bool = False) -> None:
    """Полная очистка: прокси Windows, серверы, фоновые задачи."""
    global _STATE
    state = _STATE
    if cfg is None and state is not None:
        cfg = state.cfg

    if state is not None:
        for task in list(state.tasks):
            if not task.done():
                task.cancel()
        for server in list(state.servers):
            server.close()
        if state.proxy_ctx is not None:
            try:
                state.proxy_ctx.disable()
            except Exception:
                pass
            state.proxy_ctx = None
        state.tasks.clear()
        state.servers.clear()

    if not is_android() and cfg is not None:
        try:
            from tg_bridge.system_proxy import SystemProxy, force_disable_ours

            if SystemProxy._active is not None:
                try:
                    SystemProxy._active.disable()
                except Exception:
                    pass
                SystemProxy._active = None
            force_disable_ours(cfg.host, cfg.port, cfg.http_port, cfg.pac_port)
        except Exception:
            pass

    _STATE = None
    if not quiet:
        log.status("TGonPC остановлен")


def register_exit_hooks(cfg: BridgeConfig) -> None:
    atexit.register(lambda: full_shutdown(cfg, quiet=True))

    if sys.platform != "win32":
        return

    import ctypes

    def _ctrl_handler(ctrl_type: int) -> bool:
        full_shutdown(cfg, quiet=True)
        return True

    try:
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(handler_type(_ctrl_handler), True)
    except Exception:
        pass


def apply_frozen_exe_defaults(argv: list[str]) -> list[str]:
    """Собранный .exe по умолчанию: только Telegram, без системного прокси и браузера."""
    if not getattr(sys, "frozen", False):
        return argv
    if len(argv) > 1:
        return argv
    return argv + ["--no-browser"]
