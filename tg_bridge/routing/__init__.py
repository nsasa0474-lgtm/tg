"""Маршрутизация SOCKS5-соединений: MTProto, WebSocket, relay, MTProxy."""

from tg_bridge.routing.pipe import pipe
from tg_bridge.routing.tcp_relay import handle_tcp_relay
from tg_bridge.routing.telegram import (
    handle_telegram,
    handle_telegram_with_init,
    route_telegram_connection,
)
from tg_bridge.routing.ws_bridge import bridge_tcp_ws
from tg_bridge.routing.ws_connect import try_ws_connect

__all__ = [
    "bridge_tcp_ws",
    "handle_tcp_relay",
    "handle_telegram",
    "handle_telegram_with_init",
    "pipe",
    "route_telegram_connection",
    "try_ws_connect",
]
