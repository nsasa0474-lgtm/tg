from __future__ import annotations

import logging
import re
import urllib.parse
from pathlib import Path

log = logging.getLogger("tg_bridge")

_EMBEDDED_FILE = Path(__file__).with_name("mtproxy_embedded.txt")
_IP = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

_INLINE: tuple[str, ...] = (
    "https://t.me/proxy?server=5.181.0.202&port=443&secret=eec11798ab008831b474066c9e1ebf5c96617669746f2e7275",
    "https://t.me/proxy?server=185.117.0.248&port=443&secret=eed451f808fd60ed2c45f11d38fdbc87c57961686f6f2e636f6d",
    "https://t.me/proxy?server=46.225.29.180&port=443&secret=ee636c6f7564666c6172652e636f6db6",
    "https://t.me/proxy?server=116.203.134.165&port=443&secret=ee636c6f7564666c6172652e636f6db6",
    "https://t.me/proxy?server=178.104.98.160&port=443&secret=ee636c6f7564666c6172652e636f6db6",
    "https://t.me/proxy?server=95.216.222.63&port=443&secret=ee85f51151981bd69a6281f9e85395161a676f6f676c65617069732e636f6d",
    "https://t.me/proxy?server=132.243.213.216&port=443&secret=eea3f41c6c1aefca10e6a8c366158ae25d706574726f766963682e7275",
    "https://t.me/proxy?server=78.17.71.42&port=443&secret=eeec75b855ebcc01c982f3e013af8ed92a7777772e79616e6465782e7275",
    "https://t.me/proxy?server=103.110.64.212&port=443&secret=eeb4559cb6722f727d849090621e7aba8f79616e6465782e7275",
    "https://t.me/proxy?server=fastproxy.chunkycorp.shop&port=443&secret=ee3a3365be03d6bc13518d65e70a3146c2706574726f766963682e7275",
)

_lock = __import__("threading").Lock()
_working: dict | None = None
_verified = False
_MAX_PROBE = 120


def _parse_proxy_line(line: str) -> dict | None:
    line = line.strip()
    if "server=" not in line:
        return None
    try:
        q = line.split("?", 1)[-1]
        params = urllib.parse.parse_qs(q)
        host = (params.get("server") or [""])[0].strip().rstrip(".")
        port_s = (params.get("port") or ["443"])[0].strip()
        secret = (params.get("secret") or [""])[0].strip()
        if not host or not secret:
            return None
        port = int(port_s)
        if port <= 0 or port > 65535:
            return None
        return {"host": host, "port": port, "secret": secret}
    except Exception:
        return None


def _sort_proxies(proxies: list[dict]) -> list[str]:
    # Домены раньше «голых» IP: 103.110.* часто даёт ложный TCP без MTProto.
    def key(p: dict) -> tuple[int, str]:
        h = str(p["host"])
        return (1 if _IP.match(h) else 0, h)

    ordered = sorted(proxies, key=key)
    lines: list[str] = []
    for p in ordered[:_MAX_PROBE]:
        lines.append("%s|%d|%s" % (p["host"], int(p["port"]), p["secret"]))
    return lines


def load_proxy_list() -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    sources: list[str] = list(_INLINE)
    if _EMBEDDED_FILE.is_file():
        try:
            sources.extend(_EMBEDDED_FILE.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError as exc:
            log.warning("embedded mtproxy file: %s", exc)
    try:
        from tg_bridge.mtproxy_fetch import fetch_remote_proxies

        remote = fetch_remote_proxies(300)
        for p in remote:
            line = "https://t.me/proxy?server=%s&port=%d&secret=%s" % (
                p["host"],
                int(p["port"]),
                p["secret"],
            )
            sources.append(line)
        log.info("mtproxy remote merged: %d", len(remote))
    except Exception as exc:
        log.warning("mtproxy remote fetch: %s", exc)
    for line in sources:
        p = _parse_proxy_line(line)
        if not p:
            continue
        key = (p["host"], p["port"], p["secret"])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def build_mtproxy_batch() -> str:
    return "\n".join(_sort_proxies(load_proxy_list()))


def get_working_mtproxy() -> dict | None:
    with _lock:
        return dict(_working) if _working else None


def is_mtproxy_active() -> bool:
    with _lock:
        return _verified and _working is not None


def note_mtproxy_success(proxy: dict) -> None:
    global _working, _verified
    with _lock:
        _working = dict(proxy)
        _verified = True
    from tg_bridge.relay_pool import _set_progress

    _set_progress("ok")
    log.info("MTProxy OK: %s:%s", proxy["host"], proxy["port"])


def note_mtproxy_failure() -> None:
    global _working, _verified
    with _lock:
        _working = None
        _verified = False


def apply_found_line(found: str) -> bool:
    """host|port|secret из Java."""
    found = (found or "").strip()
    if not found:
        return False
    parts = found.split("|", 2)
    if len(parts) < 3:
        return False
    try:
        proxy = {"host": parts[0], "port": int(parts[1]), "secret": parts[2]}
    except ValueError:
        return False
    note_mtproxy_success(proxy)
    return True


def sync_progress_from_java() -> str:
    try:
        from tg_bridge.android_java import tunnel_network_helper

        Helper = tunnel_network_helper()
        prog = str(Helper.getMtProxyProgress())
        found = str(Helper.getMtProxyFound())
        if found:
            apply_found_line(found)
        if prog:
            from tg_bridge.relay_pool import _set_progress

            _set_progress(prog)
        return prog
    except Exception as exc:
        log.warning("sync java mtproxy: %s", exc)
        return ""


def is_java_scan_running() -> bool:
    try:
        from tg_bridge.android_java import tunnel_network_helper

        return bool(tunnel_network_helper().isMtProxyScanRunning())
    except Exception:
        return False


def wait_java_mtproxy_scan(max_sec: float = 120.0) -> dict | None:
    import time

    deadline = time.time() + max_sec
    while is_java_scan_running() and time.time() < deadline:
        sync_progress_from_java()
        if is_mtproxy_active():
            return get_working_mtproxy()
        time.sleep(0.15)
    sync_progress_from_java()
    return get_working_mtproxy()


def find_working_mtproxy(timeout_ms: int = 2000) -> dict | None:
    if is_mtproxy_active():
        return get_working_mtproxy()
    wait_java_mtproxy_scan(5.0)
    return get_working_mtproxy()


def get_mtproxy_tg_uri() -> str:
    p = get_working_mtproxy()
    if not p:
        return ""
    from urllib.parse import quote

    return "tg://proxy?server=%s&port=%d&secret=%s" % (
        quote(str(p["host"]), safe=""),
        int(p["port"]),
        quote(str(p["secret"]), safe=""),
    )


def find_working_mtproxy_sync(timeout_ms: int = 2000) -> dict | None:
    return find_working_mtproxy(timeout_ms)


def start_mtproxy_retry_loop() -> None:
    pass
