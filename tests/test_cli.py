from __future__ import annotations

from tg_bridge.cli import parse_cli
from tg_bridge.config import DEFAULT_RELAY_IP


def test_cli_defaults() -> None:
    parsed = parse_cli(["tg_bridge", "--no-browser", "--no-tg-link"])
    assert parsed.cfg.host == "127.0.0.1"
    assert parsed.cfg.port == 1080
    assert parsed.cfg.dc_relay_ips[2] == DEFAULT_RELAY_IP
    assert parsed.mode == "pc"
    assert parsed.state.auto_tg is False
    assert parsed.state.auto_browser is False


def test_cli_lan_binds_all_interfaces() -> None:
    parsed = parse_cli(["tg_bridge", "--lan", "--no-browser", "--no-tg-link"])
    assert parsed.cfg.host == "0.0.0.0"


def test_cli_custom_relay_ip() -> None:
    parsed = parse_cli(
        ["tg_bridge", "--relay-ip", "149.154.167.51", "--no-browser", "--no-tg-link"]
    )
    assert all(ip == "149.154.167.51" for ip in parsed.cfg.dc_relay_ips.values())
