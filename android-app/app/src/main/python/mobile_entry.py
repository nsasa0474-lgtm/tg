"""Точка входа Chaquopy — запуск SOCKS5-моста."""
from __future__ import annotations

import threading

from tg_bridge.mobile import MobileBridge

_bridge: MobileBridge | None = None
_ready_event = threading.Event()
_start_lock = threading.Lock()


def start_bridge() -> None:
    global _bridge
    with _start_lock:
        if _bridge is not None and _bridge.is_alive:
            return
        _ready_event.clear()
        from tg_bridge.relay_pool import reset_probe_state

        reset_probe_state()

        def _warm_mtproxy_list() -> None:
            try:
                from tg_bridge.mtproxy_pool import build_mtproxy_batch

                build_mtproxy_batch()
            except Exception:
                pass

        import threading

        threading.Thread(target=_warm_mtproxy_list, name="mtproxy-warm", daemon=True).start()

        _bridge = MobileBridge(on_ready=lambda: _ready_event.set())
        _bridge.start()


def start_exit_probe() -> None:
    """Проба: Java scan стартует из TgonpcService; здесь только wait в фоне."""
    if _bridge is None or not _bridge.ready:
        return

    def _on_found(endpoint: str) -> None:
        if _bridge is not None:
            _bridge.relay_ip = endpoint

    from tg_bridge.relay_pool import kick_exit_probe

    kick_exit_probe(on_found=_on_found)


def get_mtproxy_batch() -> str:
    from tg_bridge.mtproxy_pool import build_mtproxy_batch

    return build_mtproxy_batch()


def apply_mtproxy_found(found: str) -> bool:
    from tg_bridge.mtproxy_pool import apply_found_line

    return apply_found_line(found)


def sync_from_java() -> str:
    from tg_bridge.mtproxy_pool import sync_progress_from_java

    return sync_progress_from_java()


def start_bridge_sync(timeout_sec: float = 180.0) -> str:
    try:
        start_bridge()
        if not _ready_event.wait(timeout=timeout_sec):
            if _bridge is not None and _bridge.error:
                return _bridge.error
            return "SOCKS5 не ответил за %ss" % int(timeout_sec)
        if _bridge is not None and _bridge.ready:
            return ""
        if _bridge is not None and _bridge.error:
            return _bridge.error
        return "SOCKS5 не готов"
    except Exception as exc:
        return str(exc)


def stop_bridge() -> None:
    global _bridge
    _ready_event.clear()
    if _bridge is None:
        return
    _bridge.stop()
    _bridge = None


def is_bridge_ready() -> bool:
    return _bridge is not None and _bridge.is_alive and _bridge.ready


def probe_socks5(timeout_sec: float = 3.0) -> bool:
    if _bridge is None or not _bridge.ready:
        return False
    import socket

    port = int(_bridge.port)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout_sec)
    try:
        sock.connect(("127.0.0.1", port))
        sock.sendall(b"\x05\x01\x00")
        return sock.recv(2) == b"\x05\x00"
    except OSError:
        return False
    finally:
        try:
            sock.close()
        except OSError:
            pass


def get_bridge_error() -> str:
    if _bridge is None:
        return ""
    return str(_bridge.error or "")


def get_socks_port() -> int:
    if _bridge is None:
        return 1080
    return int(_bridge.port)


def get_working_relay_ip() -> str:
    from tg_bridge.relay_pool import get_working_relay

    r = get_working_relay()
    if r:
        return r
    if _bridge is not None and _bridge.relay_ip:
        return str(_bridge.relay_ip)
    return ""


def is_relay_verified() -> bool:
    from tg_bridge.relay_pool import is_relay_verified as verified

    return verified()


def get_relay_progress() -> str:
    from tg_bridge.relay_pool import get_probe_progress
    from tg_bridge.platform import is_android

    if is_android():
        try:
            sync_from_java()
        except Exception:
            pass
    p = get_probe_progress()
    if p:
        return p
    if not is_bridge_ready():
        return "запуск SOCKS…"
    return "SOCKS ✓ → поиск…"


def get_exit_mode() -> str:
    from tg_bridge.relay_pool import get_exit_mode as mode

    return mode()


def get_mtproxy_tg_uri() -> str:
    from tg_bridge.mtproxy_pool import get_mtproxy_tg_uri as uri

    return uri()
