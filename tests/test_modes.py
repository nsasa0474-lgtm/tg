from __future__ import annotations

import pytest

from tg_bridge.modes import build_mode_flags, resolve_mode


@pytest.mark.parametrize(
    ("raw", "resolved"),
    [
        ("default", "pc"),
        ("pc", "pc"),
        ("socks", "socks"),
    ],
)
def test_resolve_mode(raw: str, resolved: str) -> None:
    assert resolve_mode(raw) == resolved


def test_pc_mode_defaults() -> None:
    flags = build_mode_flags(
        "pc",
        system_proxy=False,
        nat=False,
        no_tg_link=False,
        no_browser=False,
        zapret=False,
    )
    assert flags.system_proxy_enabled is False
    assert flags.use_nat is False
    assert flags.auto_tg is True
    assert flags.auto_browser is True


def test_system_mode_enables_proxy() -> None:
    flags = build_mode_flags(
        "system",
        system_proxy=False,
        nat=False,
        no_tg_link=False,
        no_browser=False,
        zapret=False,
    )
    assert flags.system_proxy_enabled is True
    assert flags.auto_tg is False


def test_vpn_mode_enables_nat() -> None:
    flags = build_mode_flags(
        "vpn",
        system_proxy=False,
        nat=False,
        no_tg_link=False,
        no_browser=False,
        zapret=False,
    )
    assert flags.use_nat is True


def test_zapret_disables_browser() -> None:
    flags = build_mode_flags(
        "pc",
        system_proxy=False,
        nat=False,
        no_tg_link=False,
        no_browser=False,
        zapret=True,
    )
    assert flags.auto_browser is False
