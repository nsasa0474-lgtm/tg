from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path

import pydivert
from pydivert.consts import Direction

from tg_dpi.cidr import TargetMatcher, load_networks
from tg_dpi.hosts import host_matches_sni, load_hosts
from tg_dpi.tls_util import find_sni_hostname, is_tls_client_hello

TELEGRAM_PORTS = frozenset({443, 80, 5222, 5223})


def load_dc_ips(path: Path) -> frozenset[str]:
    ips: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ips.add(line)
    return frozenset(ips)


@dataclass
class TrafficClassifier:
    matcher: TargetMatcher
    hosts: list[str]
    dc_ips: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_files(
        cls,
        cidr_path: Path,
        hosts_path: Path,
        dc_ips_path: Path | None = None,
    ) -> TrafficClassifier:
        dc_ips: frozenset[str] = frozenset()
        if dc_ips_path and dc_ips_path.is_file():
            dc_ips = load_dc_ips(dc_ips_path)
        return cls(
            matcher=TargetMatcher(load_networks(cidr_path)),
            hosts=load_hosts(hosts_path),
            dc_ips=dc_ips,
        )

    def is_dc_ip(self, addr: str) -> bool:
        if addr in self.dc_ips:
            return True
        return self.matcher.contains(addr)

    def is_telegram_ip(self, addr: str) -> bool:
        return self.is_dc_ip(addr)

    def is_dc_flow(self, packet: pydivert.Packet) -> bool:
        """Исходящий TCP к известному DC Telegram."""
        if packet.direction != Direction.OUTBOUND or packet.tcp is None:
            return False
        return self.is_dc_ip(str(packet.dst_addr))

    def is_dc_reply(self, packet: pydivert.Packet) -> bool:
        if packet.direction != Direction.INBOUND or packet.tcp is None:
            return False
        return self.is_dc_ip(str(packet.src_addr))

    def has_telegram_sni(self, packet: pydivert.Packet) -> bool:
        payload = packet.payload or b""
        if not payload or not is_tls_client_hello(payload):
            return False
        sni = find_sni_hostname(payload)
        return bool(sni and host_matches_sni(sni, self.hosts))

    def is_relevant(self, packet: pydivert.Packet) -> bool:
        """Пакет связан с Telegram — его имеет смысл обрабатывать."""
        if packet.tcp is not None:
            if self.is_dc_flow(packet) or self.is_dc_reply(packet):
                return True
            if (
                packet.direction == Direction.OUTBOUND
                and packet.dst_port in TELEGRAM_PORTS
                and self.has_telegram_sni(packet)
            ):
                return True
        if packet.udp is not None and packet.dst_port == 53:
            return packet.direction == Direction.OUTBOUND
        return False

    # совместимость со стратегиями
    def is_telegram_flow(self, packet: pydivert.Packet) -> bool:
        return self.is_dc_flow(packet)

    def is_telegram_reply(self, packet: pydivert.Packet) -> bool:
        return self.is_dc_reply(packet)
