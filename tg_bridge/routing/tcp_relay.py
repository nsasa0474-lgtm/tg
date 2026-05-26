from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge import ip_map
from tg_bridge.config import DEFAULT_RELAY_IP
from tg_bridge.routing.pipe import pipe

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig

log = logging.getLogger("tg_bridge")


def relay_ip(cfg: BridgeConfig) -> str:
    return cfg.dc_relay_ips.get(2) or next(iter(cfg.dc_relay_ips.values()), DEFAULT_RELAY_IP)


async def handle_tcp_relay(
    tcp_reader: asyncio.StreamReader,
    tcp_writer: asyncio.StreamWriter,
    dst_host: str,
    dst_port: int,
    cfg: BridgeConfig,
    label: str,
    first: bytes = b"",
) -> None:
    """TCP через relay-IP (домены :443, Telegram :80/TLS health-check)."""
    if dst_port == 443 and ip_map.is_telegram_ip(dst_host):
        try:
            remote_r, remote_w = await asyncio.wait_for(
                asyncio.open_connection(dst_host, dst_port),
                timeout=5.0,
            )
        except OSError:
            pass
        else:
            log.debug("[%s] TLS direct %s:%s", label, dst_host, dst_port)
            if first:
                remote_w.write(first)
                await remote_w.drain()
            await asyncio.gather(pipe(tcp_reader, remote_w), pipe(remote_r, tcp_writer))
            return

    relay = relay_ip(cfg)
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(relay, dst_port),
            timeout=10.0,
        )
    except Exception as exc:
        log.warning("[%s] relay %s:%s — %s", label, relay, dst_port, exc)
        return
    if dst_port == 80:
        log.debug("[%s] relay :80 %s -> %s:%s", label, dst_host, relay, dst_port)
    else:
        log.debug("[%s] TLS relay %s:%s -> %s:%s", label, dst_host, dst_port, relay, dst_port)
    if first:
        remote_w.write(first)
        await remote_w.drain()
    await asyncio.gather(pipe(tcp_reader, remote_w), pipe(remote_r, tcp_writer))
