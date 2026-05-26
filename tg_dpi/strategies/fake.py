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


class FakeStrategy(Strategy):
    """Fake Request: фейк с битым checksum + низкий TTL + сбитый SEQ (как GoodbyeDPI -6/-7)."""

    name = "fake"

    def __init__(
        self,
        fake_ttl: int = 3,
        max_payload: int = 1200,
        wrong_seq: bool = True,
        fakes: int = 2,
        max_per_flow: int = 2,
    ) -> None:
        self.fake_ttl = fake_ttl
        self.max_payload = max_payload
        self.wrong_seq = wrong_seq
        self.fakes = max(1, fakes)
        self.max_per_flow = max_per_flow

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
        payload = packet.payload
        if not payload or len(payload) > self.max_payload:
            return None
        if not classifier.is_telegram_flow(packet):
            return None

        key = FlowKey(
            str(packet.src_addr),
            packet.src_port,
            str(packet.dst_addr),
            packet.dst_port,
        )
        n = flows.increment(key)
        if n > self.max_per_flow:
            return None

        out: list[pydivert.Packet] = []
        for i in range(self.fakes):
            decoy = clone_packet(packet)
            if decoy.ipv4 is not None:
                decoy.ipv4.ttl = self.fake_ttl + i
            if decoy.tcp is not None:
                decoy.tcp.cksum = (decoy.tcp.cksum + 1 + i) & 0xFFFF
                if self.wrong_seq:
                    decoy.tcp.seq_num = (decoy.tcp.seq_num - 4096 - i) & 0xFFFFFFFF
            out.append(decoy)
        out.append(packet)
        return out
