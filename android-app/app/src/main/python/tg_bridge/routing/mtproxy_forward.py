from __future__ import annotations

import asyncio
import logging

from tg_bridge import mtproto

log = logging.getLogger("tg_bridge")


async def try_mtproxy_forward(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    init: bytes,
    label: str,
) -> bool:
    from tg_bridge.mtproxy_client import open_mtproxy
    from tg_bridge.mtproxy_pool import get_working_mtproxy

    proxy = get_working_mtproxy()
    if not proxy:
        return False

    host = str(proxy["host"])
    port = int(proxy["port"])
    secret = str(proxy["secret"])
    dc_info = mtproto.extract_dc(init)
    dc = dc_info[0] if dc_info else 2
    log.debug("[%s] MTProxy → %s:%s DC%d", label, host, port, dc)
    try:
        remote = await asyncio.wait_for(
            open_mtproxy(host, port, secret, 25.0, bind_network=True, dc=dc),
            timeout=30.0,
        )
    except Exception as exc:
        log.warning("[%s] MTProxy connect %s:%s — %s", label, host, port, exc)
        return False
    try:
        await remote.write(init)
        await asyncio.gather(
            _pipe_mtproxy(reader, remote),
            _pipe_mtproxy_back(remote, writer),
        )
        return True
    except Exception as exc:
        log.warning("[%s] MTProxy pipe — %s", label, exc)
        return False
    finally:
        remote.close()


async def _pipe_mtproxy(
    reader: asyncio.StreamReader, remote: object
) -> None:
    while True:
        data = await reader.read(65536)
        if not data:
            break
        await remote.write(data)


async def _pipe_mtproxy_back(
    remote: object, writer: asyncio.StreamWriter
) -> None:
    while True:
        data = await remote.read(65536)
        if not data:
            break
        writer.write(data)
        await writer.drain()
