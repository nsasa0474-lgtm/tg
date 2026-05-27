from __future__ import annotations

import asyncio
import logging
import ssl
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

log = logging.getLogger("tg_bridge")

_RESET_ERRORS = frozenset({10053, 10054})  # WinError: connection reset / aborted


def is_conn_reset(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
        return True
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) in _RESET_ERRORS:
        return True
    return False


def is_harmless_close(exc: BaseException | None) -> bool:
    """Штатное закрытие сессии — не логировать как ошибку."""
    if exc is None:
        return False
    if isinstance(exc, (asyncio.CancelledError, GeneratorExit, EOFError)):
        return True
    if isinstance(exc, ssl.SSLError):
        return True
    if isinstance(exc, RuntimeError) and "GeneratorExit" in str(exc):
        return True
    if isinstance(exc, asyncio.IncompleteReadError):
        return True
    msg = str(exc).upper()
    if any(
        token in msg
        for token in (
            "APPLICATION_DATA_AFTER_CLOSE_NOTIFY",
            "CLOSE_NOTIFY",
            "SHUTDOWN",
        )
    ):
        return True
    return is_conn_reset(exc)


def install_quiet_asyncio_handler() -> None:
    """Не печатать ERROR при штатном обрыве TCP (Windows Proactor)."""

    def _handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
        exc = context.get("exception")
        if is_harmless_close(exc):
            return
        msg = context.get("message") or ""
        if "connection_lost" in msg and is_harmless_close(exc):
            return
        if "GeneratorExit" in msg:
            return
        loop.default_exception_handler(context)

    try:
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(_handler)
    except RuntimeError:
        pass


async def safe_close(writer: asyncio.StreamWriter | None) -> None:
    if writer is None:
        return
    try:
        transport = writer.transport
        if transport is not None and not transport.is_closing():
            # TLS (WS): abort без unwrap — иначе SSLError в логе при штатном обрыве
            if transport.get_extra_info("sslcontext") is not None:
                transport.abort()
            elif not writer.is_closing():
                writer.close()
        elif not writer.is_closing():
            writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=3.0)
        except TimeoutError:
            if transport is not None:
                transport.abort()
    except (GeneratorExit, RuntimeError):
        pass
    except Exception as exc:
        if not is_harmless_close(exc):
            raise


async def wait_socks5_ready(host: str, port: int, timeout: float = 15.0) -> bool:
    """Дождаться SOCKS5 перед tg:// (иначе Telegram отключает прокси)."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=1.0,
            )
            writer.write(b"\x05\x01\x00")
            await writer.drain()
            resp = await asyncio.wait_for(reader.readexactly(2), timeout=2.0)
            await safe_close(writer)
            if resp == b"\x05\x00":
                log.status("SOCKS5 готов (%s:%s)", host, port)
                return True
        except Exception:
            pass
        await asyncio.sleep(0.15)
    log.warning("SOCKS5 не ответил за %ss", timeout)
    return False


async def wait_exit_ready(timeout: float = 40.0) -> bool:
    """Дождаться relay/MTProxy перед tg:// — иначе Telegram отключает SOCKS."""
    from tg_bridge.relay_pool import get_probe_progress, is_relay_verified

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last_log = 0.0
    while loop.time() < deadline:
        if is_relay_verified():
            log.status("Выход готов")
            return True
        prog = get_probe_progress()
        now = loop.time()
        if prog and now - last_log > 3.0:
            log.status("Поиск выхода: %s", prog)
            last_log = now
        await asyncio.sleep(0.2)
    ok = is_relay_verified()
    if not ok:
        log.warning(
            "Выход не найден за %ss — Telegram может отключить прокси. "
            "Подождите «ok» в логе или перезапустите.",
            int(timeout),
        )
    return ok
