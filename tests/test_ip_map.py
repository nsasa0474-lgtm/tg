from __future__ import annotations

import pytest

from tg_bridge import ip_map


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("149.154.167.220", (2, False)),
        ("149.154.175.52", (1, True)),
        ("91.105.192.100", (2, True)),
    ],
)
def test_dc_from_ip_known(ip: str, expected: tuple[int, bool]) -> None:
    assert ip_map.dc_from_ip(ip) == expected


def test_dc_from_ip_unknown() -> None:
    assert ip_map.dc_from_ip("8.8.8.8") is None


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("web.telegram.org", True),
        ("kws2.web.telegram.org", True),
        ("example.com", False),
        ("149.154.167.220", False),
    ],
)
def test_is_telegram_host(host: str, expected: bool) -> None:
    assert ip_map.is_telegram_host(host) is expected


def test_is_telegram_ip_dc_address() -> None:
    assert ip_map.is_telegram_ip("149.154.167.220") is True
    assert ip_map.is_telegram_ip("1.1.1.1") is False


@pytest.mark.parametrize(
    ("domain", "dc", "expected"),
    [
        ("kws2.web.telegram.org", 2, True),
        ("kws2-1.web.telegram.org", 2, True),
        ("kws3.web.telegram.org", 2, False),
    ],
)
def test_ws_domain_matches_dc(domain: str, dc: int, expected: bool) -> None:
    assert ip_map.ws_domain_matches_dc(domain, dc) is expected


def test_ws_domains_media_order() -> None:
    assert ip_map.ws_domains(2, False)[0] == "kws2.web.telegram.org"
    assert ip_map.ws_domains(2, True)[0] == "kws2-1.web.telegram.org"
