from __future__ import annotations

import asyncio

from tg_bridge.netutil import is_harmless_close, safe_close


async def pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        if not is_harmless_close(exc):
            raise
    finally:
        await safe_close(writer)
