from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert

from tg_dpi.conn_track import FlowTracker
from tg_dpi.flow_registry import FlowRegistry
from tg_dpi.strategies.base import Strategy
from tg_dpi.strategies.dc import DcStrategy
from tg_dpi.strategies.dns import DnsStrategy
from tg_dpi.strategies.passive import PassiveStrategy
from tg_dpi.strategies.syn_fake import SynFakeStrategy

if TYPE_CHECKING:
    from tg_dpi.traffic import TrafficClassifier


class AggressiveStrategy(Strategy):
    """DNS → passive → syn_fake → dc (data)."""

    name = "aggressive"

    def __init__(self, fake_ttl: int = 4) -> None:
        self._registry = FlowRegistry()
        self._chain: list[Strategy] = [
            DnsStrategy(),
            PassiveStrategy(registry=self._registry),
            SynFakeStrategy(fakes=4, fake_ttl=2),
            DcStrategy(fake_ttl=fake_ttl, fakes=3),
        ]
        self._trackers = [FlowTracker() for _ in self._chain]

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        for strategy, ft in zip(self._chain, self._trackers, strict=True):
            result = strategy.process(packet, classifier=classifier, flows=ft)
            if result is not None:
                return result
        return None
