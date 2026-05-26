from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert
from pydivert.consts import Direction

from tg_dpi.conn_track import FlowKey
from tg_dpi.packet_util import clone_packet
from tg_dpi.strategies.base import Strategy

if TYPE_CHECKING:
    from tg_dpi.conn_track import FlowTracker
    from tg_dpi.traffic import TrafficClassifier

# MTProto на 443: не режем TLS/ClientHello — только fake + disorder (как для бинарного протокола)
_MTPROTO_MARKERS = (0xEF, 0xDD, 0xEE, 0xDA, 0xDB)


class DcStrategy(Strategy):
    """
    Только трафик к DC IP (149.154.*, 91.108.*, …).
    Fake Request без split — split ломает MTProto handshake.
    """

    name = "dc"

    def __init__(self, fake_ttl: int = 4, fakes: int = 3) -> None:
        self.fake_ttl = fake_ttl
        self.fakes = fakes

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        if packet.direction != Direction.OUTBOUND:
            return None
        if packet.tcp is None or packet.tcp.syn or packet.tcp.fin or packet.tcp.rst:
            return None
        if not classifier.is_dc_flow(packet):
            return None

        payload = packet.payload
        if not payload or len(payload) > 2048:
            return None

        key = FlowKey(
            str(packet.src_addr),
            packet.src_port,
            str(packet.dst_addr),
            packet.dst_port,
        )
        n = flows.increment(key)
        if n > 4:
            return None

        # Первые пакеты MTProto — только fake; дальше — лёгкий split на 1 байт (abridged 0xEF…)
        if n == 1 or payload[0] not in _MTPROTO_MARKERS:
            return self._fake_only(packet)
        if n <= 3 and len(payload) > 4:
            from tg_dpi.packet_util import split_tcp

            return split_tcp(packet, 1, reverse=False)
        return None

    def _fake_only(self, packet: pydivert.Packet) -> list[pydivert.Packet]:
        out: list[pydivert.Packet] = []
        for i in range(self.fakes):
            d = clone_packet(packet)
            if d.ipv4 is not None:
                d.ipv4.ttl = self.fake_ttl + i
            if d.tcp is not None:
                d.tcp.cksum = (d.tcp.cksum + 7 + i) & 0xFFFF
                d.tcp.seq_num = (d.tcp.seq_num - 8192 - i * 100) & 0xFFFFFFFF
            out.append(d)
        out.append(packet)
        return out
