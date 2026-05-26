from __future__ import annotations

import tg_bridge.handler as handler
from tg_bridge.connect import is_telegram_target
from tg_bridge.routing import (
    bridge_tcp_ws,
    handle_tcp_relay,
    handle_telegram,
    handle_telegram_with_init,
    pipe,
    route_telegram_connection,
    try_ws_connect,
)


def test_handler_reexports_match_routing() -> None:
    assert handler.pipe is pipe
    assert handler.route_telegram_connection is route_telegram_connection
    assert handler.handle_tcp_relay is handle_tcp_relay
    assert handler.try_ws_connect is try_ws_connect
    assert handler.bridge_tcp_ws is bridge_tcp_ws
    assert handler.handle_telegram is handle_telegram
    assert handler.handle_telegram_with_init is handle_telegram_with_init


def test_is_telegram_target() -> None:
    assert is_telegram_target("149.154.167.220") is True
    assert is_telegram_target("api.telegram.org") is True
    assert is_telegram_target("google.com") is False
