from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge import ip_map
from tg_bridge.handler import pipe, route_telegram_connection

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig

log = logging.getLogger("tg_bridge")


async def passthrough(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    label: str,
    cfg: BridgeConfig | None = None,
) -> None:
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=10.0,
        )
    except OSError as exc:
        if cfg is not None and port in (80, 443, 5222, 8888):
            from tg_bridge.handler import handle_tcp_relay

            log.debug("[%s] passthrough fail %s:%s → relay", label, host, port)
            await handle_tcp_relay(reader, writer, host, port, cfg, label)
            return
        log.warning("[%s] passthrough %s:%s — %s", label, host, port, exc)
        return
    await asyncio.gather(pipe(reader, remote_w), pipe(remote_r, writer))


def is_telegram_target(host: str) -> bool:
    return ip_map.is_telegram_ip(host) or ip_map.is_telegram_host(host)


async def dispatch(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    cfg: BridgeConfig,
    label: str,
) -> None:
    if is_telegram_target(host):
        if port != 80:
            log.debug("[%s] -> %s:%s", label, host, port)
        await route_telegram_connection(reader, writer, host, port, cfg, label)
    else:
        log.debug("[%s] passthrough %s:%s", label, host, port)
        await passthrough(reader, writer, host, port, label, cfg)
