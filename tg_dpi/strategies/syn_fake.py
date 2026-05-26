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


class SynFakeStrategy(Strategy):
    """Перед исходящим SYN к DC — фейковые SYN (TTL/checksum), обход active DPI на handshake."""

    name = "syn_fake"

    def __init__(self, fakes: int = 4, fake_ttl: int = 2) -> None:
        self.fakes = fakes
        self.fake_ttl = fake_ttl

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        if packet.direction != Direction.OUTBOUND:
            return None
        if packet.tcp is None:
            return None
        if not (packet.tcp.syn and not packet.tcp.ack):
            return None
        if not classifier.is_dc_flow(packet):
            return None

        key = FlowKey(
            str(packet.src_addr),
            packet.src_port,
            str(packet.dst_addr),
            packet.dst_port,
        )
        if flows.count(key) > 0:
            return None
        flows.increment(key)

        out: list[pydivert.Packet] = []
        for i in range(self.fakes):
            d = clone_packet(packet)
            if d.ipv4 is not None:
                d.ipv4.ttl = self.fake_ttl + i
            if d.tcp is not None:
                d.tcp.cksum = (d.tcp.cksum + 11 + i) & 0xFFFF
            out.append(d)
        out.append(packet)
        return out
