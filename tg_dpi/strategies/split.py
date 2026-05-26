from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert
from pydivert.consts import Direction

from tg_dpi.conn_track import FlowKey
from tg_dpi.packet_util import split_tcp
from tg_dpi.strategies.base import Strategy
from tg_dpi.tls_util import split_at_sni

if TYPE_CHECKING:
    from tg_dpi.conn_track import FlowTracker
    from tg_dpi.traffic import TrafficClassifier


class SplitStrategy(Strategy):
    """TCP fragmentation: режем ClientHello / MTProto, опционально reverse order."""

    name = "split"

    def __init__(
        self,
        split_at: int = 2,
        max_payload: int = 1200,
        reverse: bool = True,
        auto_sni: bool = True,
        max_per_flow: int = 3,
    ) -> None:
        self.split_at = max(1, split_at)
        self.max_payload = max_payload
        self.reverse = reverse
        self.auto_sni = auto_sni
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

        pos = split_at_sni(payload, self.split_at) if self.auto_sni else self.split_at
        # на 2-м и 3-м пакете пробуем другие позиции
        if n == 2:
            pos = 1
        elif n >= 3:
            pos = min(3, len(payload) - 1)

        if len(payload) <= pos:
            return None

        return split_tcp(packet, pos, reverse=self.reverse)
