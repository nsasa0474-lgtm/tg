from __future__ import annotations

import hashlib
import os
import socket
import struct
from typing import Callable

import pyaes

from tg_bridge.mtproxy_client import parse_mtproxy_secret
from tg_bridge.mtproto import _AesCtr

PROTO_PADDED = struct.pack("<I", 0xDDDDDDDD)
TLS_VER = b"\x03\x03"
TLS_CCS = b"\x14" + TLS_VER + b"\x00\x01\x01"


def _proxy_secret_key(secret: str) -> bytes:
    raw = parse_mtproxy_secret(secret)
    if secret.strip().lower().startswith(("ee", "dd")) and len(raw) > 16:
        return raw[1:17]
    if len(raw) >= 16:
        return raw[:16]
    return raw


def _sha256(*parts: bytes) -> bytes:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.digest()


def _generate_init() -> bytearray:
    for _ in range(32):
        init = bytearray(os.urandom(64))
        first = struct.unpack_from("<I", init, 0)[0]
        second = struct.unpack_from("<I", init, 4)[0]
        if first in (
            0xEFEFEFEF,
            0xEEEEEEEE,
            0xDDDDDDDD,
            0x44414548,
            0x54534F50,
            0x20544547,
            0x4954504F,
            0x02010316,
        ):
            continue
        if second == 0:
            continue
        return init
    return bytearray(os.urandom(64))


def _obfs_header(proxy_key: bytes, dc: int, proto: bytes = PROTO_PADDED) -> tuple[bytes, _AesCtr, _AesCtr]:
    init = _generate_init()
    init[56:60] = proto
    struct.pack_into("<h", init, 60, dc)

    rev = bytes(reversed(init[:56]))
    dec_key = _sha256(rev[8:40], proxy_key)
    dec_iv = rev[40:56]

    out_key = _sha256(bytes(init[8:40]), proxy_key)
    out_iv = bytes(init[40:56])
    out_enc = _AesCtr(out_key, out_iv)

    encrypted = out_enc.update(bytes(init))
    header = bytearray(init[:56])
    header[56:64] = encrypted[56:64]

    return bytes(header), _AesCtr(out_key, out_iv), _AesCtr(dec_key, dec_iv)


def _read_tls_records(sock: socket.socket, min_payload: int = 64) -> None:
    got = 0
    while got < min_payload:
        hdr = _recv_exact(sock, 5)
        length = struct.unpack(">H", hdr[3:5])[0]
        payload = _recv_exact(sock, length)
        got += len(payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise OSError("unexpected EOF")
        buf += chunk
    return buf


def _wrap_tls_app(data: bytes, first: bool) -> bytes:
    out = b""
    if first:
        out += TLS_CCS
    rec = b"\x17" + TLS_VER + struct.pack(">H", len(data)) + data
    return out + rec


class MtProxySocket:
    """MTProxy (ee/dd) → MTProto stream после handshake."""

    __slots__ = ("_sock", "_enc", "_dec")

    def __init__(self, sock: socket.socket, enc: _AesCtr, dec: _AesCtr) -> None:
        self._sock = sock
        self._enc = enc
        self._dec = dec

    def sendall(self, data: bytes) -> None:
        enc = self._enc.update(data)
        self._sock.sendall(enc)

    def recv(self, n: int) -> bytes:
        raw = self._sock.recv(n)
        if not raw:
            return raw
        return self._dec.update(raw)

    def settimeout(self, t: float | None) -> None:
        self._sock.settimeout(t)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass


def connect_mtproxy_tunnel(
    host: str,
    port: int,
    secret: str,
    dc: int,
    timeout: float = 20.0,
    *,
    bind_cb: Callable[[socket.socket], None] | None = None,
) -> MtProxySocket:
    payload = parse_mtproxy_secret(secret)
    if not payload:
        raise OSError("bad mtproxy secret")
    proxy_key = _proxy_secret_key(secret)
    s_lower = secret.strip().lower()
    fake_tls = s_lower.startswith("ee")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if bind_cb:
            bind_cb(sock)
        sock.connect((host, port))
        sock.sendall(payload)
        if fake_tls:
            _read_tls_records(sock, 80)
            header, enc, dec = _obfs_header(proxy_key, dc)
            sock.sendall(_wrap_tls_app(header, first=True))
        else:
            header, enc, dec = _obfs_header(proxy_key, dc)
            sock.sendall(header)

        return MtProxySocket(sock, enc, dec)
    except Exception:
        sock.close()
        raise
