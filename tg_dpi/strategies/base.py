from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pydivert

    from tg_dpi.conn_track import FlowTracker
    from tg_dpi.traffic import TrafficClassifier


class Strategy(ABC):
    name: str

    @abstractmethod
    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        """
        None  — пакет без изменений
        []    — дроп
        [..]  — отправить вместо оригинала
        """
