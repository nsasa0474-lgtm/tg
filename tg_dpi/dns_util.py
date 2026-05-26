from __future__ import annotations

from tg_dpi.hosts import host_matches_sni


def _read_name(data: bytes, offset: int) -> tuple[str, int] | None:
    labels: list[str] = []
    pos = offset
    jumped = False
    jump_end = offset
    for _ in range(128):
        if pos >= len(data):
            return None
        length = data[pos]
        if length == 0:
            pos += 1
            name = ".".join(labels)
            return name, (jump_end if jumped else pos)
        if length & 0xC0 == 0xC0:
            if pos + 1 >= len(data):
                return None
            ptr = ((length & 0x3F) << 8) | data[pos + 1]
            if not jumped:
                jump_end = pos + 2
            pos = ptr
            jumped = True
            continue
        pos += 1
        if pos + length > len(data):
            return None
        labels.append(data[pos : pos + length].decode("ascii", errors="ignore"))
        pos += length
    return None


def dns_query_names(payload: bytes) -> list[str]:
    """Имена из вопросов DNS (QUERY)."""
    if len(payload) < 12:
        return []
    qdcount = int.from_bytes(payload[4:6], "big")
    if qdcount == 0:
        return []
    names: list[str] = []
    pos = 12
    for _ in range(min(qdcount, 8)):
        parsed = _read_name(payload, pos)
        if not parsed:
            break
        name, pos = parsed
        if name:
            names.append(name.lower())
        if pos + 4 > len(payload):
            break
        pos += 4  # QTYPE + QCLASS
    return names


def query_matches_hosts(payload: bytes, hosts: list[str]) -> bool:
    for name in dns_query_names(payload):
        if host_matches_sni(name, hosts):
            return True
    return False
