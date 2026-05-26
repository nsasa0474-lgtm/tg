from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert

from tg_dpi.conn_track import FlowTracker
from tg_dpi.strategies.base import Strategy
from tg_dpi.strategies.dns import DnsStrategy
from tg_dpi.strategies.fake import FakeStrategy
from tg_dpi.strategies.passive import PassiveStrategy
from tg_dpi.strategies.split import SplitStrategy

if TYPE_CHECKING:
    from tg_dpi.traffic import TrafficClassifier


class ComboStrategy(Strategy):
    """DNS + passive + fake + split (мягче aggressive на passive)."""

    name = "combo"

    def __init__(self, split_at: int = 2, fake_ttl: int = 3) -> None:
        self._chain: list[Strategy] = [
            DnsStrategy(),
            PassiveStrategy(aggressive=False),
            SplitStrategy(split_at=split_at, reverse=True, auto_sni=True),
            FakeStrategy(fake_ttl=fake_ttl),
        ]
        self._flow_trackers = [FlowTracker() for _ in self._chain]

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        for strategy, ft in zip(self._chain, self._flow_trackers, strict=True):
            result = strategy.process(packet, classifier=classifier, flows=ft)
            if result is not None:
                return result
        return None
