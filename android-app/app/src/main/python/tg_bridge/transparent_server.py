from __future__ import annotations

import asyncio
import logging

from typing import TYPE_CHECKING

from tg_bridge.config import BridgeConfig
from tg_bridge.handler import route_telegram_connection
from tg_bridge.nat_table import DEFAULT_DST, TRANSPARENT_PORT, lookup_orig
from tg_bridge.netutil import safe_close

if TYPE_CHECKING:
    from tg_bridge.lifecycle import RuntimeState

log = logging.getLogger("tg_bridge")


async def handle_transparent_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    cfg: BridgeConfig,
    orig_dst: tuple[str, int],
) -> None:
    peer = writer.get_extra_info("peername")
    label = f"nat:{peer[0]}:{peer[1]}->{orig_dst[0]}:{orig_dst[1]}"
    try:
        await route_telegram_connection(reader, writer, orig_dst[0], orig_dst[1], cfg, label)
    except Exception:
        log.exception("[%s] ошибка", label)
    finally:
        await safe_close(writer)


async def run_transparent_server(
    cfg: BridgeConfig,
    state: RuntimeState | None = None,
    port: int = TRANSPARENT_PORT,
) -> None:
    async def _client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        if not peer:
            writer.close()
            return
        orig = lookup_orig(peer[0], peer[1]) or DEFAULT_DST
        log.info("NAT connect %s:%s -> %s:%s", peer[0], peer[1], orig[0], orig[1])
        await handle_transparent_client(reader, writer, cfg, orig)

    server = await asyncio.start_server(_client, "127.0.0.1", port)
    if state is not None:
        state.servers.append(server)
    log.info("Прозрачный TCP (NAT) на 127.0.0.1:%s", port)
    async with server:
        await server.serve_forever()
