from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge import ip_map, mtproto
from tg_bridge.platform import is_android
from tg_bridge.routing.mtproxy_forward import try_mtproxy_forward
from tg_bridge.routing.pipe import pipe
from tg_bridge.routing.tcp_relay import handle_tcp_relay
from tg_bridge.routing.ws_bridge import bridge_tcp_ws
from tg_bridge.routing.ws_connect import try_ws_connect

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig

log = logging.getLogger("tg_bridge")

# TLS record types (RFC 5246) — браузер / HTTPS, не MTProto
_TLS_FIRST_BYTES = frozenset({0x14, 0x15, 0x16, 0x17})


async def route_telegram_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    dst_host: str,
    dst_port: int,
    cfg: BridgeConfig,
    label: str,
) -> None:
    """MTProto (64 байта), TLS (браузер) или HTTP :80 через relay."""
    if dst_port == 80:
        await handle_tcp_relay(reader, writer, dst_host, dst_port, cfg, label)
        return
    if dst_port not in (443, 5222, 8888):
        from tg_bridge.connect import passthrough

        await passthrough(reader, writer, dst_host, dst_port, label, cfg)
        return
    if dst_port != 443:
        init = await asyncio.wait_for(reader.readexactly(64), timeout=15.0)
        await handle_telegram_with_init(reader, writer, dst_host, dst_port, cfg, label, init)
        return

    first = await reader.read(1)
    if not first:
        return
    if first[0] in _TLS_FIRST_BYTES:
        await handle_tcp_relay(reader, writer, dst_host, dst_port, cfg, label, first)
        return
    try:
        rest = await asyncio.wait_for(reader.readexactly(63), timeout=15.0)
    except (asyncio.TimeoutError, asyncio.IncompleteReadError):
        await handle_tcp_relay(reader, writer, dst_host, dst_port, cfg, label, first)
        return
    init = first + rest
    await handle_telegram_with_init(reader, writer, dst_host, dst_port, cfg, label, init)


async def handle_telegram(
    tcp_reader: asyncio.StreamReader,
    tcp_writer: asyncio.StreamWriter,
    dst_ip: str,
    dst_port: int,
    cfg: BridgeConfig,
    label: str,
) -> None:
    init = await asyncio.wait_for(tcp_reader.readexactly(64), timeout=15.0)
    await handle_telegram_with_init(tcp_reader, tcp_writer, dst_ip, dst_port, cfg, label, init)


async def handle_telegram_with_init(
    tcp_reader: asyncio.StreamReader,
    tcp_writer: asyncio.StreamWriter,
    dst_ip: str,
    dst_port: int,
    cfg: BridgeConfig,
    label: str,
    init: bytes,
) -> None:

    if init.startswith((b"GET ", b"POST ", b"HEAD ")):
        log.debug("[%s] HTTP transport — не поддерживается", label)
        return

    dc_info = mtproto.extract_dc(init)
    patched = False
    if dc_info is None:
        mapped = ip_map.dc_from_ip(dst_ip)
        if mapped is None:
            log.warning("[%s] неизвестный DC для %s", label, dst_ip)
            await _tcp_direct(tcp_reader, tcp_writer, dst_ip, dst_port, init, label)
            return
        dc, is_media = mapped
        init_b = bytearray(init)
        mtproto.patch_dc(init_b, dc, is_media)
        init = bytes(init_b)
        patched = True
        dc_info = (dc, is_media)
    else:
        dc, is_media = dc_info

    media = " media" if is_media else ""
    proto = mtproto._proto_from_init(init)
    proto_name = {0xEFEFEFEF: "abr", 0xEEEEEEEE: "int", 0xDDDDDDDD: "pad"}.get(
        proto, hex(proto)
    )
    log.debug(
        "[%s] DC%d%s proto=%s dst=%s:%s",
        label,
        dc,
        media,
        proto_name,
        dst_ip,
        dst_port,
    )

    if is_android():
        from tg_bridge.mtproxy_pool import is_mtproxy_active

        if is_mtproxy_active():
            if await try_mtproxy_forward(tcp_reader, tcp_writer, init, label):
                return
            log.warning("[%s] MTProxy forward failed", label)
            return

    streams = await try_ws_connect(cfg, dc, is_media, label)
    if streams is None and dc != 2:
        log.debug("[%s] WS DC%d недоступен, пробуем мост DC2", label, dc)
        init2 = bytearray(init)
        mtproto.patch_dc(init2, 2, is_media)
        streams = await try_ws_connect(cfg, 2, is_media, label)
        if streams:
            init = bytes(init2)
            dc = 2
    if streams is None:
        log.debug("[%s] повтор WS", label)
        streams = await try_ws_connect(cfg, dc, is_media, label)
    if streams is None:
        if await try_mtproxy_forward(tcp_reader, tcp_writer, init, label):
            return
        if is_android():
            log.warning("[%s] WS и MTProxy недоступны на Android", label)
            return
        log.warning("[%s] WS и MTProxy недоступны, прямой TCP %s:%s", label, dst_ip, dst_port)
        await _tcp_direct(tcp_reader, tcp_writer, dst_ip, dst_port, init, label)
        return

    ws_reader, ws_writer = streams
    await bridge_tcp_ws(tcp_reader, tcp_writer, ws_reader, ws_writer, init, label)


async def _tcp_direct(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    host: str,
    port: int,
    init: bytes,
    label: str,
) -> None:
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=10.0,
        )
    except Exception as exc:
        log.warning("[%s] TCP %s:%s — %s", label, host, port, exc or type(exc).__name__)
        return
    remote_w.write(init)
    await remote_w.drain()
    await asyncio.gather(pipe(reader, remote_w), pipe(remote_r, writer))
