from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from tg_bridge import ip_map, websocket as ws
from tg_bridge.config import DEFAULT_RELAY_IP
from tg_bridge.platform import is_android
from tg_bridge.relay_pool import (
    apply_relay_to_config,
    kick_exit_probe,
    note_relay_failure,
    note_relay_success,
    relay_candidates,
    start_background_probe,
)

if TYPE_CHECKING:
    from tg_bridge.config import BridgeConfig

log = logging.getLogger("tg_bridge")


def _err_text(exc: Exception) -> str:
    text = str(exc).strip()
    return text or type(exc).__name__


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

    per_timeout = min(cfg.connect_timeout, 12.0)

    ep = get_working_endpoint()
    if ep:
        connect_host, ep_domain = ep
        try_list = [(connect_host, d) for d in domains]
        if ip_map.ws_domain_matches_dc(ep_domain, dc) and (
            connect_host,
            ep_domain,
        ) not in try_list:
            try_list.insert(0, (connect_host, ep_domain))
        for host, domain in try_list:
            try:
                log.debug("[%s] WS try %s via %s", label, domain, host)
                streams = await ws.ws_connect(host, domain, per_timeout)
                note_relay_success(host, domain, direct=any(c.isalpha() for c in host))
                apply_relay_to_config(cfg, host)
                log.debug("[%s] WS ok %s via %s", label, domain, host)
                return streams
            except ws.WsError as exc:
                if exc.is_redirect:
                    log.warning("[%s] redirect %s -> %s", label, domain, exc.location)
                    continue
                log.debug("[%s] WS fail %s via %s: %s", label, domain, host, _err_text(exc))
            except Exception as exc:
                log.debug("[%s] WS fail %s via %s: %s", label, domain, host, _err_text(exc))
        kick_exit_probe()

    preferred = cfg.dc_relay_ips.get(dc) or cfg.dc_relay_ips.get(2) or DEFAULT_RELAY_IP
    for rip in relay_candidates(preferred):
        for domain in domains:
            try:
                log.debug("[%s] WS try %s via %s", label, domain, rip)
                streams = await ws.ws_connect(rip, domain, per_timeout)
                note_relay_success(rip, domain, direct=False)
                apply_relay_to_config(cfg, rip)
                log.debug("[%s] WS ok %s via %s", label, domain, rip)
                return streams
            except ws.WsError as exc:
                if exc.is_redirect:
                    log.warning("[%s] redirect %s -> %s", label, domain, exc.location)
                    continue
                log.debug("[%s] WS fail %s via %s: %s", label, domain, rip, _err_text(exc))
            except Exception as exc:
                log.debug("[%s] WS fail %s via %s: %s", label, domain, rip, _err_text(exc))
        note_relay_failure(rip)

    for domain in ip_map.ws_domains(dc, is_media):
        if domain in seen:
            continue
        try:
            log.debug("[%s] WS direct try %s", label, domain)
            streams = await ws.ws_connect(domain, domain, per_timeout)
            note_relay_success(domain, domain, direct=True)
            apply_relay_to_config(cfg, domain)
            log.debug("[%s] WS ok %s (direct)", label, domain)
            return streams
        except ws.WsError as exc:
            if exc.is_redirect:
                continue
            log.debug("[%s] direct %s: %s", label, domain, exc)
        except Exception as exc:
            log.debug("[%s] direct %s: %s", label, domain, exc)
        note_relay_failure(domain)

    from tg_bridge.relay_pool import is_relay_verified

    if not is_relay_verified():
        start_background_probe()
    return None
