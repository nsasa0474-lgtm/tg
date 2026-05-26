from __future__ import annotations

import asyncio
import logging

from tg_bridge import mtproto, websocket as ws
from tg_bridge.netutil import is_harmless_close, safe_close

log = logging.getLogger("tg_bridge")


async def bridge_tcp_ws(
    tcp_reader: asyncio.StreamReader,
    tcp_writer: asyncio.StreamWriter,
    ws_reader: asyncio.StreamReader,
    ws_writer: asyncio.StreamWriter,
    init: bytes,
    label: str,
) -> None:
    splitter = mtproto.MsgSplitter(init)
    await ws.send_frame(ws_writer, init)

    async def tcp_to_ws() -> None:
        try:
            while True:
                chunk = await tcp_reader.read(262144)
                if not chunk:
                    for tail in splitter.flush():
                        await ws.send_frame(ws_writer, tail)
                    break
                parts = splitter.split(chunk)
                if not parts:
                    continue
                for part in parts:
                    await ws.send_frame(ws_writer, part)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not is_harmless_close(exc):
                log.warning("[%s] tcp->ws: %s", label, exc)

    async def ws_to_tcp() -> None:
        down = 0
        try:
            while True:
                frame = await ws.recv_frame(ws_reader)
                if frame is None:
                    break
                kind, payload = frame
                if kind == "ping":
                    ws_writer.write(ws.build_frame(ws.OP_PONG, payload, True))
                    await ws_writer.drain()
                elif kind in ("data", "other") and payload:
                    tcp_writer.write(payload)
                    await tcp_writer.drain()
                    down += len(payload)
        except asyncio.IncompleteReadError:
            log.debug("[%s] ws закрыт", label)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            if not is_harmless_close(exc):
                log.warning("[%s] ws->tcp: %s", label, exc)

    t_up = asyncio.create_task(tcp_to_ws(), name=f"{label}:up")
    t_down = asyncio.create_task(ws_to_tcp(), name=f"{label}:down")
    try:
        done, pending = await asyncio.wait(
            {t_up, t_down},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None and not is_harmless_close(exc):
                log.warning("[%s] %s", label, exc)
    except asyncio.CancelledError:
        t_up.cancel()
        t_down.cancel()
        await asyncio.gather(t_up, t_down, return_exceptions=True)
    finally:
        await safe_close(ws_writer)
        await safe_close(tcp_writer)
    log.debug("[%s] сессия закрыта", label)
