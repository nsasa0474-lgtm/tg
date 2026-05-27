from __future__ import annotations

import asyncio
import logging
import re
import socket
import threading
from typing import TYPE_CHECKING

from tg_bridge.mtproxy_secret import parse_mtproxy_secret
from tg_bridge.platform import is_android

if TYPE_CHECKING:
    from tg_bridge.mtproxy_tunnel import MtProxySocket

log = logging.getLogger("tg_bridge")

_HEX = re.compile(r"^[0-9a-fA-F]+$")
_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

def _resolve_ipv4(host: str, timeout: float) -> str | None:
    if _IP.match(host):
        return host
    out: list[str | None] = [None]

    def _run() -> None:
        try:
            infos = socket.getaddrinfo(
                host, 443, socket.AF_INET, socket.SOCK_STREAM
            )
            if infos:
                out[0] = infos[0][4][0]
        except OSError:
            out[0] = None

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(max(0.5, timeout))
    return out[0]


def connect_mtproxy_sync(
    host: str,
    port: int,
    secret: str,
    timeout: float = 2.0,
    *,
    bind_network: bool = False,
    strict: bool = True,
) -> socket.socket | None:
    """Синхронное подключение — не зависает на asyncio (Android)."""
    try:
        payload = parse_mtproxy_secret(secret)
    except Exception:
        return None
    if not payload:
        return None

    ip = _resolve_ipv4(host, min(timeout, 1.5))
    if not ip:
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if bind_network and is_android():
            try:
                from tg_bridge.android_net import try_bind_socket

                try_bind_socket(sock)
            except Exception:
                pass
        sock.connect((ip, port))
        sock.sendall(payload)
        sock.settimeout(min(timeout, 2.0))
        buf = b""
        try:
            while len(buf) < 128:
                chunk = sock.recv(512)
                if not chunk:
                    break
                buf += chunk
                if len(buf) >= 80:
                    break
        except OSError:
            pass
        if len(buf) < 40:
            sock.close()
            return None
        if buf[:1] == b"H" or buf.startswith(b"HTTP"):
            sock.close()
            return None
        s = secret.strip().lower()
        if s.startswith(("ee", "dd")):
            min_len = 80 if strict else 32
            if buf[0] != 0x16 or len(buf) < min_len:
                sock.close()
                return None
        sock.settimeout(timeout)
        return sock
    except OSError:
        try:
            sock.close()
        except OSError:
            pass
        return None


class _AsyncMtProxy:
    __slots__ = ("_t", "_loop")

    def __init__(self, tunnel: MtProxySocket) -> None:
        self._t = tunnel
        self._loop = asyncio.get_running_loop()

    async def read(self, n: int = 65536) -> bytes:
        return await self._loop.run_in_executor(None, self._t.recv, n)

    async def write(self, data: bytes) -> None:
        await self._loop.run_in_executor(None, self._t.sendall, data)

    def close(self) -> None:
        self._t.close()


async def open_mtproxy(
    host: str,
    port: int,
    secret: str,
    timeout: float = 15.0,
    *,
    bind_network: bool = True,
    dc: int = 2,
) -> _AsyncMtProxy:
    from tg_bridge.mtproxy_tunnel import connect_mtproxy_tunnel

    loop = asyncio.get_running_loop()

    def _connect() -> MtProxySocket:
        bind_cb = None
        if bind_network and is_android():
            from tg_bridge.android_net import try_bind_socket

            bind_cb = try_bind_socket
        return connect_mtproxy_tunnel(
            host, port, secret, dc, timeout, bind_cb=bind_cb
        )

    tunnel = await asyncio.wait_for(loop.run_in_executor(None, _connect), timeout + 2.0)
    return _AsyncMtProxy(tunnel)
