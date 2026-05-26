from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass
class ProbeResult:
    name: str
    host: str
    port: int
    ok: bool
    detail: str


def _tcp_probe(name: str, host: str, port: int = 443, timeout: float = 4.0) -> ProbeResult:
    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    try:
        s = socket.socket(family, socket.SOCK_STREAM)
        s.settimeout(timeout)
        if family == socket.AF_INET6:
            s.connect((host, port, 0, 0))
        else:
            s.connect((host, port))
        s.close()
        return ProbeResult(name, host, port, True, "TCP OK")
    except OSError as exc:
        return ProbeResult(name, host, port, False, str(exc))


def run_network_diagnose() -> list[ProbeResult]:
    return [
        _tcp_probe("DC-2 IPv4", "149.154.167.51"),
        _tcp_probe("DC-1 IPv4", "149.154.175.50"),
        _tcp_probe("DC IPv4 (log)", "149.154.175.57"),
        _tcp_probe("DC-alt IPv4", "95.161.76.100"),
        _tcp_probe("DC-2 IPv6", "2001:0b28:f23d:f002::a"),
        _tcp_probe("DC-4 IPv6", "2001:067c:04e8:f004::9"),
        _tcp_probe("kws1.web", "149.154.174.100"),
        _tcp_probe("Microsoft (ref)", "20.190.177.19"),
    ]


def summarize(results: list[ProbeResult]) -> tuple[str, bool]:
    """
    Returns (message, tg_dpi_can_help).
    tg_dpi_can_help = хотя бы один TG endpoint доступен по TCP.
    """
    tg = [r for r in results if "Microsoft" not in r.name]
    ms = [r for r in results if "Microsoft" in r.name]
    tg_ok = [r for r in tg if r.ok]
    ms_ok = [r for r in ms if r.ok]

    if tg_ok:
        return (
            "Часть серверов Telegram доступна по TCP — имеет смысл tg_dpi (DPI/поддельные RST).",
            True,
        )

    lines = [
        "Серверы Telegram (149.154.* / IPv6) по TCP НЕДОСТУПНЫ — это блокировка IP, не DPI.",
        "tg_dpi меняет пакеты локально и не заменит VPN/MTProxy/другой канал.",
    ]
    if ms_ok:
        lines.append(
            "Доступен только Microsoft (20.190.*) — Telegram к нему MTProto не шлёт; "
            "в логе будут SYN без ответа (как сейчас)."
        )
    lines.append(
        "Что реально помогает: мобильный интернет, другой провайдер, MTProxy в настройках TG, VPN."
    )
    return ("\n".join(lines), False)
