from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import pydivert
from pydivert.consts import Direction

from tg_dpi.conn_track import FlowTracker
from tg_dpi.flow_registry import FlowRegistry
from tg_dpi.strategies.base import Strategy
from tg_dpi.traffic import TrafficClassifier

log = logging.getLogger(__name__)

WINDIVERT_FILTER = (
    "(outbound and tcp and (tcp.DstPort == 443 or tcp.DstPort == 80 or tcp.DstPort == 5222))"
    " or (inbound and tcp and (tcp.Rst or (tcp.Syn and tcp.Ack)))"
    " or (inbound and icmp)"
    " or (outbound and udp and udp.DstPort == 53)"
)


@dataclass
class EngineStats:
    captured: int = 0
    dropped: int = 0
    modified: int = 0
    reinjected: int = 0
    bypassed: int = 0
    fast_syn: int = 0
    syn_seen: int = 0
    synack_seen: int = 0
    rst_dropped: int = 0
    errors: int = 0
    started_at: float = field(default_factory=time.monotonic)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_at


class DpiEngine:
    def __init__(
        self,
        strategy: Strategy,
        classifier: TrafficClassifier,
        *,
        debug: bool = False,
    ) -> None:
        self.strategy = strategy
        self.classifier = classifier
        self.flows = FlowTracker()
        self.registry = FlowRegistry()
        self.stats = EngineStats()
        self.debug = debug
        self._debug_left = 40

    def run(self) -> None:
        log.info("Стратегия: %s", self.strategy.name)
        log.info("Фильтр: %s", WINDIVERT_FILTER)
        log.info("DC IP: %s", ", ".join(sorted(self.classifier.dc_ips)[:8]))
        log.info("Остановка: Ctrl+C")

        with pydivert.WinDivert(WINDIVERT_FILTER) as divert:
            for packet in divert:
                self.stats.captured += 1

                if self._fast_path(packet, divert):
                    continue

                if not self.classifier.is_relevant(packet):
                    divert.send(packet)
                    self.stats.bypassed += 1
                    continue

                self._track_handshake(packet)
                self._debug(packet)

                try:
                    outcome = self.strategy.process(
                        packet,
                        classifier=self.classifier,
                        flows=self.flows,
                    )
                except Exception:
                    log.exception("Ошибка обработки пакета")
                    self.stats.errors += 1
                    divert.send(packet)
                    self.stats.reinjected += 1
                    continue

                if outcome is None:
                    divert.send(packet)
                    self.stats.reinjected += 1
                elif len(outcome) == 0:
                    self.stats.dropped += 1
                    self.stats.rst_dropped += 1
                    self._debug(packet, "DROP")
                else:
                    self.stats.modified += 1
                    self._debug(packet, f"MODx{len(outcome)}")
                    for pkt in outcome:
                        divert.send(pkt)

                if self.stats.captured % 4000 == 0:
                    self._log_stats()

    def _fast_path(self, packet: pydivert.Packet, divert: pydivert.WinDivert) -> bool:
        """Быстрый пропуск SYN-ACK без очереди в Python."""
        if packet.tcp is None:
            return False
        if (
            packet.direction == Direction.INBOUND
            and packet.tcp.syn
            and packet.tcp.ack
            and self.classifier.is_dc_reply(packet)
        ):
            self.stats.synack_seen += 1
            divert.send(packet)
            self.stats.fast_syn += 1
            if self.debug and self._debug_left > 0:
                self._debug_left -= 1
                log.info(
                    "SYN-ACK in %s:%s -> %s:%s",
                    packet.src_addr,
                    packet.src_port,
                    packet.dst_addr,
                    packet.dst_port,
                )
            return True
        return False

    def _track_handshake(self, packet: pydivert.Packet) -> None:
        if packet.tcp is None:
            return
        if (
            packet.direction == Direction.OUTBOUND
            and packet.tcp.syn
            and not packet.tcp.ack
            and self.classifier.is_dc_flow(packet)
        ):
            self.stats.syn_seen += 1

    def _debug(self, packet: pydivert.Packet, tag: str = "SEE") -> None:
        if not self.debug or self._debug_left <= 0:
            return
        if not (
            self.classifier.is_dc_flow(packet)
            or self.classifier.is_dc_reply(packet)
        ):
            return
        self._debug_left -= 1
        extra = ""
        if packet.tcp:
            if packet.tcp.syn:
                extra += " SYN"
            if packet.tcp.ack:
                extra += " ACK"
            if packet.tcp.rst:
                extra += " RST"
            if packet.payload:
                extra += f" data={len(packet.payload)}"
        log.info(
            "%s %s %s:%s -> %s:%s%s",
            tag,
            "out" if packet.direction == Direction.OUTBOUND else "in",
            packet.src_addr,
            packet.src_port,
            packet.dst_addr,
            packet.dst_port,
            extra,
        )

    def _log_stats(self) -> None:
        s = self.stats
        log.info(
            "stats: syn=%d synack=%d mod=%d drop_rst=%d (%.0fs)",
            s.syn_seen,
            s.synack_seen,
            s.modified,
            s.rst_dropped,
            s.elapsed(),
        )
        if s.syn_seen > 20 and s.synack_seen == 0 and s.elapsed() > 8:
            log.warning(
                "Нет ни одного SYN-ACK от DC — блокировка IP на стороне провайдера. "
                "tg_dpi не сможет поднять MTProto."
            )
