from __future__ import annotations

from typing import TYPE_CHECKING

import pydivert
from pydivert.consts import Direction

from tg_dpi.dns_util import query_matches_hosts
from tg_dpi.strategies.base import Strategy

if TYPE_CHECKING:
    from tg_dpi.conn_track import FlowTracker
    from tg_dpi.traffic import TrafficClassifier

# Yandex DNS на нестандартном порту — типичный обход DNS-poisoning (как в GoodbyeDPI)
DEFAULT_DNS_ADDR = "77.88.8.8"
DEFAULT_DNS_PORT = 1253


class DnsStrategy(Strategy):
    """Перенаправляет DNS-запросы к доменам Telegram на чистый резолвер."""

    name = "dns"

    def __init__(
        self,
        dns_addr: str = DEFAULT_DNS_ADDR,
        dns_port: int = DEFAULT_DNS_PORT,
    ) -> None:
        self.dns_addr = dns_addr
        self.dns_port = dns_port

    def process(
        self,
        packet: pydivert.Packet,
        *,
        classifier: TrafficClassifier,
        flows: FlowTracker,
    ) -> list[pydivert.Packet] | None:
        if packet.direction != Direction.OUTBOUND:
            return None
        if packet.udp is None or packet.dst_port != 53:
            return None
        payload = packet.payload
        if not payload or not query_matches_hosts(payload, classifier.hosts):
            return None

        packet.dst_addr = self.dns_addr
        packet.dst_port = self.dns_port
        packet.recalculate_checksums()
        return [packet]
