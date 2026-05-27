from __future__ import annotations

import asyncio
import logging
import struct
from typing import TYPE_CHECKING

from tg_bridge.connect import dispatch
from tg_bridge.netutil import is_harmless_close, safe_close

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig
    from tg_bridge.lifecycle import RuntimeState

log = logging.getLogger("tg_bridge")


def _socks5_reply(status: int = 0) -> bytes:
    return struct.pack("!BBBB", 5, status, 0, 1) + b"\x00\x00\x00\x00" + b"\x00\x00"


async def _parse_host_port(atyp: int, reader: asyncio.StreamReader) -> tuple[str, int] | None:
    if atyp == 1:
        raw = await reader.readexactly(4)
        host = ".".join(str(b) for b in raw)
    elif atyp == 3:
        n = (await reader.readexactly(1))[0]
        host = (await reader.readexactly(n)).decode("ascii", errors="replace")
    elif atyp == 4:
        import ipaddress

        raw = await reader.readexactly(16)
        host = str(ipaddress.IPv6Address(raw))
    else:
        return None
    port = struct.unpack("!H", await reader.readexactly(2))[0]
    return host, port


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    cfg: BridgeConfig,
) -> None:
    peer = writer.get_extra_info("peername")
    label = f"socks:{peer[0]}:{peer[1]}" if peer else "socks:?"

    try:
        ver, nmethods = struct.unpack("!BB", await reader.readexactly(2))
        if ver != 5:
            return
        await reader.readexactly(nmethods)
        writer.write(b"\x05\x00")
        await writer.drain()

        ver, cmd, _, atyp = struct.unpack("!BBBB", await reader.readexactly(4))
        if cmd != 1:
            writer.write(_socks5_reply(7))
            await writer.drain()
            return

        parsed = await _parse_host_port(atyp, reader)
        if parsed is None:
            writer.write(_socks5_reply(8))
            await writer.drain()
            return
        host, port = parsed

        writer.write(_socks5_reply(0))
        await writer.drain()
        await dispatch(reader, writer, host, port, cfg, label)

    except asyncio.IncompleteReadError:
        pass
    except Exception as exc:
        if not is_harmless_close(exc):
            log.exception("[%s] ошибка", label)
    finally:
        await safe_close(writer)


async def run_server(cfg: BridgeConfig, state: RuntimeState | None = None) -> None:
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, cfg),
        cfg.host,
        cfg.port,
    )
    if state is not None:
        state.servers.append(server)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    log.status("SOCKS5 слушает %s", addrs)
    async with server:
        await server.serve_forever()
