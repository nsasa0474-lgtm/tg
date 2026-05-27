"""Обратная совместимость: публичный API handler перенесён в tg_bridge.routing."""

from tg_bridge.routing import (
    bridge_tcp_ws,
    handle_tcp_relay,
    handle_telegram,
    handle_telegram_with_init,
    pipe,
    route_telegram_connection,
    try_ws_connect,
)

__all__ = [
    "bridge_tcp_ws",
    "handle_tcp_relay",
    "handle_telegram",
    "handle_telegram_with_init",
    "pipe",
    "route_telegram_connection",
    "try_ws_connect",
]
