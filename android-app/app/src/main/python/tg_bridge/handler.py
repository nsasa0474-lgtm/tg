from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge import ip_map, mtproto, websocket as ws
from tg_bridge.config import DEFAULT_RELAY_IP
from tg_bridge.netutil import is_harmless_close, safe_close
from tg_bridge.platform import is_android
from tg_bridge.relay_pool import (
    apply_relay_to_config,
    note_relay_failure,
    note_relay_success,
    relay_candidates,
    start_background_probe,
)

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig

log = logging.getLogger("tg_bridge")

# TLS record types (RFC 5246) — браузер / HTTPS, не MTProto
_TLS_FIRST_BYTES = frozenset({0x14, 0x15, 0x16, 0x17})


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        if not is_harmless_close(exc):
            raise
    finally:
        await safe_close(writer)


async def bridge_tcp_ws(
    tcp_reader: asyncio.StreamReader,
    tcp_writer: asyncio.StreamWriter,
    ws_reader: asyncio.StreamReader,
    ws_writer: asyncio.StreamWriter,
    init: bytes,
    label: str,
) -> None:
    splitter = mtproto.MsgSplitter(init)
    await ws.send_frame(ws_writer, init)

    async def tcp_to_ws() -> None:
        try:
            while True:
                chunk = await tcp_reader.read(262144)
                if not chunk:
                    for tail in splitter.flush():
                        await ws.send_frame(ws_writer, tail)
                    break
                parts = splitter.split(chunk)
                if not parts:
                    continue
                for part in parts:
                    await ws.send_frame(ws_writer, part)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not is_harmless_close(exc):
                log.warning("[%s] tcp->ws: %s", label, exc)

    async def ws_to_tcp() -> None:
        down = 0
        try:
            while True:
                frame = await ws.recv_frame(ws_reader)
                if frame is None:
                    break
                kind, payload = frame
                if kind == "ping":
                    ws_writer.write(ws.build_frame(ws.OP_PONG, payload, True))
                    await ws_writer.drain()
                elif kind in ("data", "other") and payload:
                    tcp_writer.write(payload)
                    await tcp_writer.drain()
                    down += len(payload)
        except asyncio.IncompleteReadError:
            log.debug("[%s] ws закрыт", label)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not is_harmless_close(exc):
                log.warning("[%s] ws->tcp: %s", label, exc)

    t_up = asyncio.create_task(tcp_to_ws(), name=f"{label}:up")
    t_down = asyncio.create_task(ws_to_tcp(), name=f"{label}:down")
    try:
        done, pending = await asyncio.wait(
            {t_up, t_down},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None and not is_harmless_close(exc):
                log.warning("[%s] %s", label, exc)
    except asyncio.CancelledError:
        t_up.cancel()
        t_down.cancel()
        await asyncio.gather(t_up, t_down, return_exceptions=True)
    finally:
        await safe_close(ws_writer)
        await safe_close(tcp_writer)
    log.debug("[%s] сессия закрыта", label)


async def try_ws_connect(
    cfg: BridgeConfig,
    dc: int,
    is_media: bool,
    label: str,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter] | None:
    if is_android():
        from tg_bridge.mtproxy_pool import is_mtproxy_active

        if is_mtproxy_active():
            return None

    from tg_bridge.relay_pool import get_working_endpoint

    seen: set[str] = set()
    domains: list[str] = []
    for d in ip_map.ws_domains(dc, is_media):
        if d not in seen:
            seen.add(d)
            domains.append(d)
    for d in ip_map.ws_domains(2, is_media):
        if d not in seen:
            seen.add(d)
            domains.append(d)

    per_timeout = min(cfg.connect_timeout, 12.0)

    ep = get_working_endpoint()
    if ep:
        connect_host, ep_domain = ep
        try_list = [(connect_host, d) for d in domains]
        if (connect_host, ep_domain) not in try_list:
            try_list.insert(0, (connect_host, ep_domain))
        for host, domain in try_list:
            try:
                log.info("[%s] WS wss://%s via %s", label, domain, host)
                streams = await ws.ws_connect(host, domain, per_timeout)
                note_relay_success(host, domain, direct=any(c.isalpha() for c in host))
                apply_relay_to_config(cfg, host)
                return streams
            except ws.WsError as exc:
                if exc.is_redirect:
                    continue
                log.warning("[%s] WS %s via %s: %s", label, domain, host, exc)
            except Exception as exc:
                log.warning("[%s] WS %s via %s: %s", label, domain, host, exc)

    preferred = cfg.dc_relay_ips.get(dc) or cfg.dc_relay_ips.get(2) or DEFAULT_RELAY_IP
    for rip in relay_candidates(preferred):
        for domain in domains:
            try:
                log.info("[%s] WS wss://%s/apiws via %s", label, domain, rip)
                streams = await ws.ws_connect(rip, domain, per_timeout)
                note_relay_success(rip, domain, direct=False)
                apply_relay_to_config(cfg, rip)
                return streams
            except ws.WsError as exc:
                if exc.is_redirect:
                    log.warning("[%s] redirect %s -> %s", label, domain, exc.location)
                    continue
                log.warning("[%s] WS %s via %s", label, exc, rip)
            except Exception as exc:
                log.warning("[%s] WS connect %s via %s: %s", label, domain, rip, exc)
        note_relay_failure(rip)

    for domain in ip_map.all_ws_endpoint_domains():
        if domain in seen:
            continue
        try:
            log.info("[%s] WS direct wss://%s", label, domain)
            streams = await ws.ws_connect(domain, domain, per_timeout)
            note_relay_success(domain, domain, direct=True)
            apply_relay_to_config(cfg, domain)
            return streams
        except ws.WsError as exc:
            if exc.is_redirect:
                continue
            log.debug("[%s] direct %s: %s", label, domain, exc)
        except Exception as exc:
            log.debug("[%s] direct %s: %s", label, domain, exc)
        note_relay_failure(domain)

    start_background_probe()
    return None


def _relay_ip(cfg: BridgeConfig) -> str:
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
    """Прозрачный TCP к relay (только домены; IP Telegram — не сюда)."""
    if ip_map.is_telegram_ip(dst_host):
        log.warning("[%s] TLS relay для IP %s пропущен", label, dst_host)
        return
    relay = _relay_ip(cfg)
    try:
        remote_r, remote_w = await asyncio.wait_for(
            asyncio.open_connection(relay, dst_port),
            timeout=10.0,
        )
    except Exception as exc:
        log.warning("[%s] relay %s:%s — %s", label, relay, dst_port, exc)
        return
    log.info("[%s] TLS relay %s:%s -> %s:%s", label, dst_host, dst_port, relay, dst_port)
    if first:
        remote_w.write(first)
        await remote_w.drain()
    await asyncio.gather(pipe(tcp_reader, remote_w), pipe(remote_r, tcp_writer))


async def route_telegram_connection(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    dst_host: str,
    dst_port: int,
    cfg: BridgeConfig,
    label: str,
) -> None:
    """MTProto (64 байта), TLS (браузер) или HTTP :80."""
    from tg_bridge.connect import passthrough

    if dst_port == 80:
        await passthrough(reader, writer, dst_host, dst_port, label)
        return
    if dst_port not in (443, 5222, 8888):
        await passthrough(reader, writer, dst_host, dst_port, label)
        return
    if dst_port != 443:
        init = await asyncio.wait_for(reader.readexactly(64), timeout=15.0)
        await handle_telegram_with_init(reader, writer, dst_host, dst_port, cfg, label, init)
        return

    # IP дата-центров Telegram — всегда MTProto, не TLS relay (иначе вечное переподключение)
    if ip_map.is_telegram_ip(dst_host):
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
    log.info(
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
            if await _try_mtproxy_forward(tcp_reader, tcp_writer, init, label):
                return
            log.warning("[%s] MTProxy forward failed", label)
            return

    streams = await try_ws_connect(cfg, dc, is_media, label)
    if streams is None and dc != 2:
        log.info("[%s] WS DC%d недоступен, пробуем мост DC2", label, dc)
        init2 = bytearray(init)
        mtproto.patch_dc(init2, 2, is_media)
        streams = await try_ws_connect(cfg, 2, is_media, label)
        if streams:
            init = bytes(init2)
            dc = 2
    if streams is None:
        if is_android():
            if await _try_mtproxy_forward(tcp_reader, tcp_writer, init, label):
                return
            log.warning("[%s] WS и MTProxy недоступны на Android", label)
            return
        log.warning("[%s] WS недоступен, прямой TCP %s:%s", label, dst_ip, dst_port)
        await _tcp_direct(tcp_reader, tcp_writer, dst_ip, dst_port, init, label)
        return

    ws_reader, ws_writer = streams
    await bridge_tcp_ws(tcp_reader, tcp_writer, ws_reader, ws_writer, init, label)


async def _try_mtproxy_forward(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    init: bytes,
    label: str,
) -> bool:
    from tg_bridge.mtproxy_client import open_mtproxy
    from tg_bridge.mtproxy_pool import get_working_mtproxy

    proxy = get_working_mtproxy()
    if not proxy:
        return False

    host = str(proxy["host"])
    port = int(proxy["port"])
    secret = str(proxy["secret"])
    dc_info = mtproto.extract_dc(init)
    dc = dc_info[0] if dc_info else 2
    log.info("[%s] MTProxy → %s:%s DC%d", label, host, port, dc)
    try:
        remote = await asyncio.wait_for(
            open_mtproxy(host, port, secret, 25.0, bind_network=True, dc=dc),
            timeout=30.0,
        )
    except Exception as exc:
        log.warning("[%s] MTProxy connect %s:%s — %s", label, host, port, exc)
        return False
    try:
        await remote.write(init)
        await asyncio.gather(
            _pipe_mtproxy(reader, remote),
            _pipe_mtproxy_back(remote, writer),
        )
        return True
    except Exception as exc:
        log.warning("[%s] MTProxy pipe — %s", label, exc)
        return False
    finally:
        remote.close()


async def _pipe_mtproxy(
    reader: asyncio.StreamReader, remote: object
) -> None:
    while True:
        data = await reader.read(65536)
        if not data:
            break
        await remote.write(data)


async def _pipe_mtproxy_back(
    remote: object, writer: asyncio.StreamWriter
) -> None:
    while True:
        data = await remote.read(65536)
        if not data:
            break
        writer.write(data)
        await writer.drain()


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
