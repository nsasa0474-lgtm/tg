from __future__ import annotations

import logging
import re
import urllib.parse
import urllib.request

log = logging.getLogger("tg_bridge")

_PROXY_LINE = re.compile(
    r"(?:https?://t\.me/proxy\?|tg://proxy\?)([^\s#\"']+)",
    re.IGNORECASE,
)
_SERVER = re.compile(r"server=([^&\s]+)", re.IGNORECASE)

_SOURCES: tuple[str, ...] = (
    "https://raw.githubusercontent.com/ALIILAPRO/MTProtoProxy/main/mtproto.txt",
    "https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt",
    "https://raw.githubusercontent.com/Firmfox/Proxify/refs/heads/main/telegram_proxies/mtproto.txt",
    "https://raw.githubusercontent.com/Grim1313/mtproto-for-telegram/master/all_proxies.txt",
)

_TIMEOUT = 12.0
_MAX_LINES = 400


def _parse_proxy_url(query: str) -> dict | None:
    try:
        params = urllib.parse.parse_qs(query, keep_blank_values=False)
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


def _extract_from_text(body: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for m in _PROXY_LINE.finditer(body):
        p = _parse_proxy_url(m.group(1))
        if not p:
            continue
        key = (p["host"], p["port"], p["secret"])
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    for line in body.splitlines():
        line = line.strip()
        if "server=" not in line:
            continue
        q = line.split("?", 1)[-1] if "?" in line else line
        p = _parse_proxy_url(q)
        if not p:
            sm = _SERVER.search(line)
            if not sm:
                continue
        if p:
            key = (p["host"], p["port"], p["secret"])
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def fetch_remote_proxies(max_items: int = _MAX_LINES) -> list[dict]:
    merged: list[dict] = []
    seen: set[tuple[str, int, str]] = set()
    for url in _SOURCES:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TGonPC/1.0"},
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                body = resp.read(512_000).decode("utf-8", errors="replace")
            batch = _extract_from_text(body)
            log.info("mtproxy fetch %s: %d", url, len(batch))
            for p in batch:
                key = (p["host"], p["port"], p["secret"])
                if key in seen:
                    continue
                seen.add(key)
                merged.append(p)
                if len(merged) >= max_items:
                    return merged
        except Exception as exc:
            log.warning("mtproxy fetch %s: %s", url, exc)
    return merged
