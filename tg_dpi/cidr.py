from __future__ import annotations

import ipaddress
from pathlib import Path


def load_networks(path: Path) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        networks.append(ipaddress.ip_network(line, strict=False))
    return networks


class TargetMatcher:
    """Проверяет, относится ли IP к диапазонам Telegram."""

    def __init__(self, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> None:
        self._v4 = [n for n in networks if n.version == 4]
        self._v6 = [n for n in networks if n.version == 6]

    def contains(self, addr: str) -> bool:
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            return False
        nets = self._v4 if ip.version == 4 else self._v6
        return any(ip in net for net in nets)
