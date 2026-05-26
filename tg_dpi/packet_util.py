from __future__ import annotations

import pydivert


def clone_packet(packet: pydivert.Packet) -> pydivert.Packet:
    """Копия пакета с сохранением direction/interface (важно для WinDivert)."""
    return pydivert.Packet(
        packet.raw.tobytes(),
        interface=packet.interface,
        direction=packet.direction,
        layer=packet.layer,
    )


def split_tcp(
    packet: pydivert.Packet,
    split_at: int,
    *,
    reverse: bool = False,
) -> list[pydivert.Packet]:
    """Разрезать TCP payload на 2 сегмента (native frag)."""
    payload = packet.payload
    if not payload or len(payload) <= split_at:
        return [packet]

    part1, part2 = payload[:split_at], payload[split_at:]
    seq = packet.tcp.seq_num

    first = clone_packet(packet)
    first.payload = part1
    first.tcp.seq_num = seq
    first.recalculate_checksums()

    second = clone_packet(packet)
    second.payload = part2
    second.tcp.seq_num = seq + len(part1)
    second.recalculate_checksums()

    if reverse:
        return [second, first]
    return [first, second]
