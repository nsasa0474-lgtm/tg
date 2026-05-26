from __future__ import annotations

import logging
import socket
import threading

import pydivert
from pydivert.consts import Direction

from tg_bridge import ip_map
from tg_bridge.nat_table import TRANSPARENT_PORT, register_flow

log = logging.getLogger("tg_bridge")

TG_PORTS = frozenset({80, 443, 5222, 8888})

# loopback обязателен для перенаправления на 127.0.0.1
FILTER = (
    "(outbound and !loopback and tcp and "
    "(tcp.DstPort == 443 or tcp.DstPort == 80 or tcp.DstPort == 5222 or tcp.DstPort == 8888)) "
    f"or (loopback and tcp and (tcp.DstPort == {TRANSPARENT_PORT} or tcp.SrcPort == {TRANSPARENT_PORT}))"
)

_loopback_if: tuple[int, int] | None = None
_seen_out = 0


def _loopback_interface() -> tuple[int, int]:
    global _loopback_if
    if _loopback_if is not None:
        return _loopback_if
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("127.0.0.1", 80))
            # для reinject на loopback WinDivert часто нужен ifidx=1
    except OSError:
        pass
    _loopback_if = (1, 0)
    return _loopback_if


def _process_packet(packet: pydivert.Packet) -> list[pydivert.Packet]:
    global _seen_out
    if packet.tcp is None:
        return [packet]

    if packet.direction == Direction.OUTBOUND and not packet.is_loopback:
        dst = str(packet.dst_addr)
        dport = packet.dst_port
        if dport not in TG_PORTS or not ip_map.is_telegram_ip(dst):
            return [packet]

        _seen_out += 1
        if _seen_out <= 5 or _seen_out % 50 == 0:
            log.info("NAT перехват #%d -> 127.0.0.1:%s (%s:%s)", _seen_out, TRANSPARENT_PORT, dst, dport)

        register_flow(str(packet.src_addr), packet.src_port, dst, dport)
        packet.dst_addr = "127.0.0.1"
        packet.dst_port = TRANSPARENT_PORT
        packet.interface = _loopback_interface()
        packet.recalculate_checksums()
        return [packet]

    if packet.tcp is not None:
        src = str(packet.src_addr)
        sport = packet.src_port
        dst = str(packet.dst_addr)
        dport = packet.dst_port

        if sport == TRANSPARENT_PORT and src == "127.0.0.1":
            from tg_bridge.nat_table import lookup_orig

            orig = lookup_orig(dst, dport)
            if orig:
                packet.src_addr = orig[0]
                packet.src_port = orig[1]
                packet.interface = _loopback_interface()
                packet.recalculate_checksums()
            return [packet]

    return [packet]


def _nat_loop() -> None:
    log.info("NAT WinDivert -> 127.0.0.1:%s", TRANSPARENT_PORT)
    with pydivert.WinDivert(FILTER) as w:
        for packet in w:
            try:
                for p in _process_packet(packet):
                    w.send(p)
            except Exception:
                log.exception("NAT error")
                try:
                    w.send(packet)
                except Exception:
                    pass


def start_nat_thread() -> threading.Thread:
    t = threading.Thread(target=_nat_loop, name="tg-nat", daemon=True)
    t.start()
    return t
