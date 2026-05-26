from __future__ import annotations

import ipaddress

TG_RANGES = [
    ipaddress.ip_network("185.76.151.0/24"),
    ipaddress.ip_network("149.154.160.0/20"),
    ipaddress.ip_network("91.105.192.0/23"),
    ipaddress.ip_network("91.108.0.0/16"),
]

DC_FROM_IP: dict[str, tuple[int, bool]] = {
    "149.154.175.50": (1, False),
    "149.154.175.51": (1, False),
    "149.154.175.53": (1, False),
    "149.154.175.54": (1, False),
    "149.154.175.52": (1, True),
    "149.154.167.41": (2, False),
    "149.154.167.50": (2, False),
    "149.154.167.51": (2, False),
    "149.154.167.220": (2, False),
    "95.161.76.100": (2, False),
    "149.154.175.100": (3, False),
    "149.154.175.101": (3, False),
    "149.154.175.102": (3, True),
    "149.154.167.91": (4, False),
    "149.154.167.92": (4, False),
    "149.154.171.5": (5, False),
    "91.108.56.100": (5, False),
    "91.105.192.100": (2, True),
}


TELEGRAM_HOST_SUFFIXES = (
    ".telegram.org",
    ".telegram.me",
    ".telegram-cdn.org",
    ".t.me",
    "telegram.org",
    "telegram.me",
    "t.me",
)


def is_telegram_host(host: str) -> bool:
    h = host.lower().strip(".")
    if h in ("telegram.org", "telegram.me", "t.me"):
        return True
    return any(h.endswith(s) for s in TELEGRAM_HOST_SUFFIXES)


def is_telegram_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.version != 4:
        return False
    return any(addr in net for net in TG_RANGES)


def dc_from_ip(ip: str) -> tuple[int, bool] | None:
    return DC_FROM_IP.get(ip)


def ws_domains(dc: int, is_media: bool) -> list[str]:
    if is_media:
        return [f"kws{dc}-1.web.telegram.org", f"kws{dc}.web.telegram.org"]
    return [f"kws{dc}.web.telegram.org", f"kws{dc}-1.web.telegram.org"]


def all_ws_endpoint_domains() -> list[str]:
    """Домены для прямого WSS (обход блокировки DC IP на LTE)."""
    seen: set[str] = set()
    out: list[str] = []
    for dc in range(1, 6):
        for media in (False, True):
            for d in ws_domains(dc, media):
                if d not in seen:
                    seen.add(d)
                    out.append(d)
    for extra in (
        "zws1.web.telegram.org",
        "zws2.web.telegram.org",
        "zws1-1.web.telegram.org",
        "zws2-1.web.telegram.org",
        "pluto.web.telegram.org",
        "venus.web.telegram.org",
        "flora.web.telegram.org",
        "aurora.web.telegram.org",
        "vesta.web.telegram.org",
    ):
        if extra not in seen:
            seen.add(extra)
            out.append(extra)
    return out
