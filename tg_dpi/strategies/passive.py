from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert
from pydivert.consts import Direction

from tg_dpi.conn_track import FlowKey
from tg_dpi.flow_registry import FlowRegistry
from tg_dpi.strategies.base import Strategy

if TYPE_CHECKING:
    from tg_dpi.conn_track import FlowTracker
    from tg_dpi.traffic import TrafficClassifier

_PASSIVE_DPI_IDENTS = frozenset({0, 1})


class PassiveStrategy(Strategy):
    """Регистрирует сессии к DC; гасит RST/ICMP от DPI."""

    name = "passive"

    def __init__(self, registry: FlowRegistry | None = None) -> None:
        self.registry = registry or FlowRegistry()

    def _flow_key_inbound(self, packet: pydivert.Packet) -> FlowKey:
        return FlowKey(
            str(packet.dst_addr),
            packet.dst_port,
            str(packet.src_addr),
            packet.src_port,
        )

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        if packet.direction == Direction.OUTBOUND and packet.tcp is not None:
            if packet.tcp.syn and not packet.tcp.ack and classifier.is_dc_flow(packet):
                self.registry.add(
                    FlowKey(
                        str(packet.src_addr),
                        packet.src_port,
                        str(packet.dst_addr),
                        packet.dst_port,
                    )
                )
            return None

        if packet.direction != Direction.INBOUND:
            return None

        key = self._flow_key_inbound(packet)
        tracked = self.registry.contains(key)
        from_dc = classifier.is_dc_reply(packet)

        if not tracked and not from_dc:
            return None

        if packet.tcp is not None and packet.tcp.rst:
            return []

        if packet.icmp is not None and tracked:
            return []

        if (
            packet.tcp is not None
            and from_dc
            and packet.ipv4 is not None
            and packet.ipv4.ident in _PASSIVE_DPI_IDENTS
            and packet.tcp.rst
        ):
            return []

        return None
