from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge.pac import build_pac
from tg_bridge.netutil import safe_close

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig
    from tg_bridge.lifecycle import RuntimeState

log = logging.getLogger("tg_bridge")

_PAC_BODY: bytes = b""


def _pac_bytes(cfg: BridgeConfig) -> bytes:
    global _PAC_BODY
    text = build_pac(cfg.host, cfg.http_port, cfg.host, cfg.port)
    _PAC_BODY = text.encode("utf-8")
    return _PAC_BODY


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, cfg: BridgeConfig) -> None:
    try:
        line = await asyncio.wait_for(reader.readline(), timeout=5.0)
        if not line:
            return
        while True:
            h = await reader.readline()
            if h in (b"\r\n", b"\n", b""):
                break
        body = _pac_bytes(cfg)
        if b"proxy.pac" in line or b".pac" in line:
            hdr = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/x-ns-proxy-autoconfig\r\n"
                "Cache-Control: no-cache\r\n"
                f"Content-Length: {len(body)}\r\n\r\n"
            ).encode()
            resp = hdr + body
        else:
            resp = b"HTTP/1.1 404 Not Found\r\n\r\n"
        writer.write(resp)
        await writer.drain()
    except Exception:
        pass
    finally:
        await safe_close(writer)


async def run_pac_server(cfg: BridgeConfig, state: RuntimeState | None = None) -> None:
    port = cfg.pac_port
    _pac_bytes(cfg)
    server = await asyncio.start_server(
        lambda r, w: _handle(r, w, cfg),
        cfg.host,
        port,
    )
    if state is not None:
        state.servers.append(server)
    log.info("PAC autoconfig http://%s:%s/proxy.pac", cfg.host, port)
    async with server:
        await server.serve_forever()
