from __future__ import annotations

import asyncio
import logging
import threading

from tg_bridge import ip_map, websocket as ws
from tg_bridge.config import DEFAULT_RELAY_IP, RELAY_IP_FALLBACKS
from tg_bridge.platform import is_android

log = logging.getLogger("tg_bridge")

_PROBE_DOMAIN = "kws2.web.telegram.org"

_RELAY_PRIORITY = (
    "149.154.167.51",
    "95.161.76.100",
    "149.154.175.50",
    "149.154.175.100",
    "149.154.167.91",
    "149.154.171.5",
    "149.154.167.50",
    "149.154.167.41",
    "149.154.175.101",
    "91.108.56.100",
    "91.105.192.100",
    "149.154.167.92",
    DEFAULT_RELAY_IP,
)

_lock = threading.Lock()
_working: str | None = None
_working_domain: str | None = None
_verified = False
_probe_progress = ""
_probe_running = False


def reset_probe_state() -> None:
    global _probe_running, _probe_progress, _working, _verified, _working_domain
    with _lock:
        _probe_running = False
        _probe_progress = "инициализация"
        _working = None
        _working_domain = None
        _verified = False
    try:
        from tg_bridge.mtproxy_pool import note_mtproxy_failure

        note_mtproxy_failure()
    except Exception:
        pass


def get_probe_progress() -> str:
    with _lock:
        return _probe_progress


def get_working_endpoint() -> tuple[str, str] | None:
    with _lock:
        if not (_verified and _working):
            return None
        domain = _working_domain or _PROBE_DOMAIN
        return (_working, domain)


def get_working_relay() -> str | None:
    ep = get_working_endpoint()
    if ep:
        return ep[0]
    from tg_bridge.mtproxy_pool import get_working_mtproxy

    mp = get_working_mtproxy()
    if mp:
        return mp["host"]
    return None


def is_relay_verified() -> bool:
    from tg_bridge.mtproxy_pool import is_mtproxy_active

    if is_mtproxy_active():
        return True
    with _lock:
        return _verified and _working is not None


def get_exit_mode() -> str:
    from tg_bridge.mtproxy_pool import is_mtproxy_active

    if is_mtproxy_active():
        return "mtproxy"
    with _lock:
        if _verified and _working:
            return "relay"
    return ""


def relay_candidates(preferred: str | None = None) -> list[str]:
    ep = get_working_endpoint()
    if ep:
        preferred = ep[0]
    order: list[str] = []
    for ip in (preferred,):
        if ip and ip not in order:
            order.append(ip)
    for ip in _base_ip_candidates():
        if ip not in order:
            order.append(ip)
    return order or _base_ip_candidates()


def _base_ip_candidates() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for ip in (*_RELAY_PRIORITY, *RELAY_IP_FALLBACKS, *ip_map.DC_FROM_IP.keys()):
        if ip and ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out


def _set_progress(msg: str) -> None:
    global _probe_progress
    with _lock:
        _probe_progress = msg
    log.info("probe: %s", msg)


def note_relay_success(host: str, ws_domain: str | None = None, *, direct: bool = False) -> None:
    global _working, _working_domain, _verified
    with _lock:
        _working = host
        _working_domain = ws_domain or (host if direct else _PROBE_DOMAIN)
        _verified = True
        _probe_progress = "ok"
    log.info("endpoint OK: %s", host)


def _probe_mtproxy_path(timeout_ms: int) -> str | None:
    from tg_bridge.mtproxy_pool import (
        get_working_mtproxy,
        is_java_scan_running,
        wait_java_mtproxy_scan,
    )

    _set_progress("MTProxy…")
    mp = wait_java_mtproxy_scan(120.0)
    if mp:
        return mp["host"]
    if is_java_scan_running():
        _set_progress("MTProxy: идёт поиск…")
        return None
    _set_progress("не найден (MTProxy)")
    return None


async def _python_ws_probe(timeout_ms: int) -> str | None:
    t = timeout_ms / 1000.0
    for i, ip in enumerate(_base_ip_candidates(), start=1):
        _set_progress("IP %d/%d" % (i, len(_base_ip_candidates())))
        try:
            writer = None
            try:
                _r, writer = await asyncio.wait_for(
                    ws.ws_connect(ip, _PROBE_DOMAIN, t),
                    timeout=t + 2.0,
                )
                note_relay_success(ip, _PROBE_DOMAIN, direct=False)
                return ip
            finally:
                if writer:
                    writer.close()
                    await writer.wait_closed()
        except Exception:
            pass
    return None


def find_working_exit_sync(timeout_ms: int = 2500) -> str | None:
    global _probe_running

    if is_relay_verified():
        return get_working_relay()

    with _lock:
        if _probe_running:
            return get_working_relay()
        _probe_running = True

    try:
        _set_progress("поиск выхода…")

        # Android: Wi‑Fi — WS relay; LTE — MTProxy (+ WS если relay вдруг доступен)
        if is_android():
            cellular = True
            try:
                from tg_bridge.android_java import app_context, tunnel_network_helper

                cellular = bool(
                    tunnel_network_helper().isCellularPreferred(app_context())
                )
            except Exception:
                pass
            if not cellular:
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    hit = loop.run_until_complete(_python_ws_probe(timeout_ms))
                    if hit:
                        return hit
                finally:
                    loop.close()
            return _probe_mtproxy_path(timeout_ms)

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            hit = loop.run_until_complete(_python_ws_probe(timeout_ms))
            if hit:
                return hit
        finally:
            loop.close()
        return _probe_mtproxy_path(timeout_ms)
    except Exception as exc:
        log.exception("exit probe")
        _set_progress("ошибка: %s" % exc)
        return None
    finally:
        with _lock:
            _probe_running = False


def note_relay_failure(key: str) -> None:
    global _working, _verified
    with _lock:
        if _working == key:
            _working = None
            _verified = False


def apply_relay_to_config(cfg, ip: str) -> None:
    for dc in list(cfg.dc_relay_ips.keys()):
        cfg.dc_relay_ips[dc] = ip


def run_exit_probe(on_found=None) -> None:
    """Запуск поиска выхода — прогресс обновляется сразу в этом потоке."""
    _set_progress("SOCKS ✓ → поиск…")

    def _bg() -> None:
        try:
            hit = find_working_exit_sync(2500)
            if hit and on_found:
                on_found(hit)
        except Exception as exc:
            log.exception("exit probe bg")
            _set_progress("ошибка: %s" % exc)

    threading.Thread(target=_bg, name="exit-probe", daemon=True).start()


def kick_exit_probe(on_found=None) -> None:
    run_exit_probe(on_found=on_found)


def start_background_probe(on_found=None) -> None:
    run_exit_probe(on_found=on_found)


find_working_relay_sync = find_working_exit_sync
find_working_relay_android = find_working_exit_sync
