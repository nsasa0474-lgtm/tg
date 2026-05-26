from __future__ import annotations

from pathlib import Path


def load_hosts(path: Path) -> list[str]:
    hosts: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        hosts.append(line)
    return hosts


def host_matches_sni(hostname: str, allowed: list[str]) -> bool:
    host = hostname.lower().rstrip(".")
    for pattern in allowed:
        if host == pattern or host.endswith("." + pattern):
            return True
    return False
