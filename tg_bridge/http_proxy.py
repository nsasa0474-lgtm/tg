from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge.connect import dispatch, passthrough
from tg_bridge.netutil import safe_close

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig
    from tg_bridge.lifecycle import RuntimeState

log = logging.getLogger("tg_bridge")


async def _read_headers(reader: asyncio.StreamReader) -> None:
    while True:
        line = await reader.readline()
        if line in (b"\r\n", b"\n", b""):
            break


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    cfg: BridgeConfig,
) -> None:
    peer = writer.get_extra_info("peername")
    label = f"http:{peer[0]}:{peer[1]}" if peer else "http:?"

    try:
        line = await asyncio.wait_for(reader.readline(), timeout=30.0)
        if not line:
            return
        parts = line.decode("ascii", errors="replace").strip().split()
        if len(parts) < 2:
            return

        method, target = parts[0].upper(), parts[1]

        if method == "CONNECT":
            if ":" in target:
                host, port_s = target.rsplit(":", 1)
                port = int(port_s)
            else:
                host, port = target, 443
            await _read_headers(reader)
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            await dispatch(reader, writer, host, port, cfg, label)
            return

        # GET http://host/... — редко, но бывает у старых клиентов
        if method in ("GET", "POST", "HEAD") and target.startswith("http://"):
            from urllib.parse import urlparse

            u = urlparse(target)
            host = u.hostname or ""
            port = u.port or 80
            await _read_headers(reader)
            writer.write(b"HTTP/1.1 502 Not Implemented\r\n\r\n")
            await writer.drain()
            log.debug("[%s] HTTP proxy URL not supported: %s", label, target)
            return

        writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
        await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    except Exception:
        log.exception("[%s] ошибка", label)
    finally:
        await safe_close(writer)


async def run_http_server(cfg: BridgeConfig, state: RuntimeState | None = None) -> None:
    port = cfg.http_port
    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, cfg),
        cfg.host,
        port,
    )
    if state is not None:
        state.servers.append(server)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets or [])
    log.info("HTTP CONNECT прокси слушает %s", addrs)
    async with server:
        await server.serve_forever()
