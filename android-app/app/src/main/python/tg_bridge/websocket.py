from __future__ import annotations

import base64
import os
import ssl
import struct

import asyncio
import socket

from tg_bridge.platform import is_android

OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

def _relay_ssl_context() -> ssl.SSLContext:
    """TLS к relay-IP: сертификат на IP, SNI — домен kws*.web.telegram.org."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class WsError(Exception):
    def __init__(self, status: int, line: str, location: str | None = None) -> None:
        self.status = status
        self.line = line
        self.location = location
        super().__init__(f"HTTP {status}: {line}")

    @property
    def is_redirect(self) -> bool:
        return self.status in (301, 302, 303, 307, 308)


def build_frame(opcode: int, data: bytes, mask: bool = True) -> bytes:
    fin_opcode = 0x80 | opcode
    length = len(data)
    mask_bit = 0x80 if mask else 0
    if length < 126:
        header = struct.pack("!BB", fin_opcode, mask_bit | length)
    elif length < 65536:
        header = struct.pack("!BBH", fin_opcode, mask_bit | 126, length)
    else:
        header = struct.pack("!BBQ", fin_opcode, mask_bit | 127, length)
    if not mask:
        return header + data
    mask_key = os.urandom(4)
    masked = bytes(b ^ mask_key[i % 4] for i, b in enumerate(data))
    return header + mask_key + masked


async def _tcp_tls_connect(
    ip: str, domain: str, timeout: float
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    if is_android():
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        from tg_bridge.android_net import try_bind_socket

        try_bind_socket(sock)
        await asyncio.wait_for(loop.sock_connect(sock, (ip, 443)), timeout=timeout)
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport, _ = await loop.create_connection(lambda: protocol, sock=sock)
        tls_transport = await asyncio.wait_for(
            loop.start_tls(
                transport,
                protocol,
                _relay_ssl_context(),
                server_hostname=domain,
            ),
            timeout=timeout,
        )
        writer = asyncio.StreamWriter(tls_transport, protocol, reader, loop)
        return reader, writer

    return await asyncio.wait_for(
        asyncio.open_connection(
            ip, 443, ssl=_relay_ssl_context(), server_hostname=domain
        ),
        timeout=timeout,
    )


async def ws_connect(
    ip: str, domain: str, timeout: float = 12.0
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await _tcp_tls_connect(ip, domain, timeout)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET /apiws HTTP/1.1\r\n"
        f"Host: {domain}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n"
        f"Sec-WebSocket-Protocol: binary\r\n"
        f"Origin: https://web.telegram.org\r\n"
        f"User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36\r\n"
        f"\r\n"
    )
    writer.write(req.encode())
    await writer.drain()

    headers = b""
    while True:
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if line in (b"\r\n", b"\n", b""):
            break
        headers += line

    if not headers:
        writer.close()
        raise WsError(0, "empty response")

    first = headers.split(b"\r\n", 1)[0].decode(errors="replace")
    parts = first.split()
    status = int(parts[1]) if len(parts) >= 2 else 0
    if status == 101:
        return reader, writer

    loc = None
    for line in headers.split(b"\r\n"):
        if line.lower().startswith(b"location:"):
            loc = line.split(b":", 1)[1].strip().decode(errors="replace")
    writer.close()
    raise WsError(status, first, loc)


async def recv_frame(reader: asyncio.StreamReader) -> tuple[str, bytes] | None:
    """Читает один WS-фрейм (с поддержкой continuation)."""
    partial: list[bytes] = []

    while True:
        try:
            hdr = await reader.readexactly(2)
        except asyncio.IncompleteReadError:
            return None

        fin = (hdr[0] & 0x80) != 0
        opcode = hdr[0] & 0x0F
        masked = (hdr[1] & 0x80) != 0
        length = hdr[1] & 0x7F
        if length == 126:
            length = struct.unpack("!H", await reader.readexactly(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", await reader.readexactly(8))[0]

        mask = await reader.readexactly(4) if masked else None
        payload = await reader.readexactly(length)
        if mask:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

        if opcode == OP_CLOSE:
            return None
        if opcode == OP_PING:
            return ("ping", payload)
        if opcode == OP_PONG:
            continue

        if opcode in (OP_BINARY, OP_TEXT):
            if fin and not partial:
                return ("data", payload)
            partial.append(payload)
            if fin:
                return ("data", b"".join(partial))
            continue

        if opcode == OP_CONT:
            partial.append(payload)
            if fin and partial:
                return ("data", b"".join(partial))
            continue

        # неизвестный opcode — пропускаем
        if fin and partial:
            return ("data", b"".join(partial))


async def send_frame(writer: asyncio.StreamWriter, data: bytes) -> None:
    writer.write(build_frame(OP_BINARY, data, mask=True))
    await writer.drain()
