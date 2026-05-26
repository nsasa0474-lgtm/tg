from __future__ import annotations

import logging
import socket

from tg_bridge.platform import is_android

log = logging.getLogger("tg_bridge")


def try_bind_socket(sock: socket.socket) -> bool:
    if not is_android():
        return False
    try:
        from tg_bridge.android_java import app_context, tunnel_network_helper

        Helper = tunnel_network_helper()
        ctx = app_context()
        fd = sock.fileno()
        Helper.refreshNetwork(ctx)
        if Helper.bindSocketFdWithContext(ctx, fd):
            return True
        if Helper.bindSocketFd(fd):
            return True
        return False
    except Exception as exc:
        log.warning("android bind socket: %s", exc)
        return False
