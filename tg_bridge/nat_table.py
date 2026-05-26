from __future__ import annotations

TRANSPARENT_PORT = 10808
DEFAULT_DST = ("149.154.167.51", 443)

# (client_ip, client_port) -> (orig_dst_ip, orig_dst_port)
NAT_TABLE: dict[tuple[str, int], tuple[str, int]] = {}
NAT_BY_SPORT: dict[int, tuple[str, int]] = {}


def register_flow(client_ip: str, client_port: int, orig_ip: str, orig_port: int) -> None:
    orig = (orig_ip, orig_port)
    NAT_TABLE[(client_ip, client_port)] = orig
    NAT_BY_SPORT[client_port] = orig


def lookup_orig(peer_ip: str, peer_port: int) -> tuple[str, int] | None:
    orig = NAT_TABLE.get((peer_ip, peer_port))
    if orig:
        return orig
    orig = NAT_BY_SPORT.get(peer_port)
    if orig:
        return orig
    for (_, cport), dst in NAT_TABLE.items():
        if cport == peer_port:
            return dst
    return None
