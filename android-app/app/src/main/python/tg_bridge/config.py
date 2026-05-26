from __future__ import annotations

from dataclasses import dataclass, field

# Рабочий relay-IP (у многих провайдеров .51/.175.* режут, .167.220 — нет)
DEFAULT_RELAY_IP = "149.154.167.220"

# Запасные relay — автоподбор перебирает все (любой оператор)
RELAY_IP_FALLBACKS = (
    "149.154.167.220",
    "149.154.167.51",
    "149.154.167.50",
    "149.154.167.41",
    "149.154.167.91",
    "149.154.167.92",
    "149.154.171.5",
    "149.154.175.50",
    "149.154.175.51",
    "149.154.175.100",
    "149.154.175.101",
    "95.161.76.100",
    "91.108.56.100",
    "91.105.192.100",
)


@dataclass
class BridgeConfig:
    host: str = "127.0.0.1"
    port: int = 1080
    http_port: int = 1081
    pac_port: int = 1082
    connect_timeout: float = 12.0
    # DC → IP для TLS+WebSocket (SNI kws{N}.web.telegram.org)
    dc_relay_ips: dict[int, str] = field(
        default_factory=lambda: {1: DEFAULT_RELAY_IP, 2: DEFAULT_RELAY_IP,
                               3: DEFAULT_RELAY_IP, 4: DEFAULT_RELAY_IP,
                               5: DEFAULT_RELAY_IP}
    )
