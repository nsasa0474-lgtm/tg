from __future__ import annotations

import struct
from typing import Iterator

import pyaes

PROTO_TAGS = {0xEFEFEFEF, 0xEEEEEEEE, 0xDDDDDDDD, 0xFEFEFEFE}
PROTO_ABRIDGED = 0xEFEFEFEF
PROTO_INTERMEDIATE = 0xEEEEEEEE
PROTO_PADDED_INTERMEDIATE = 0xDDDDDDDD
ZERO_64 = b"\x00" * 64


class _AesCtr:
    """AES-CTR (совместимо с MTProto init / MsgSplitter)."""

    __slots__ = ("_aes",)

    def __init__(self, key: bytes, iv: bytes) -> None:
        ctr = pyaes.Counter(initial_value=int.from_bytes(iv, "big"))
        self._aes = pyaes.AESModeOfOperationCTR(key, ctr)

    def update(self, data: bytes) -> bytes:
        return self._aes.encrypt(data)

    def keystream(self, n: int) -> bytes:
        return self._aes.encrypt(b"\x00" * n)


def _keystream(key: bytes, iv: bytes, n: int = 64) -> bytes:
    return _AesCtr(key, iv).keystream(n)


def _proto_from_init(init: bytes) -> int:
    if len(init) < 64:
        return 0
    key = init[8:40]
    iv = init[40:56]
    stream = _keystream(key, iv)
    plain = bytes(a ^ b for a, b in zip(init[56:64], stream[56:64]))
    return struct.unpack_from("<I", plain, 0)[0]


def extract_dc(init: bytes) -> tuple[int, bool] | None:
    if len(init) < 64:
        return None
    key = init[8:40]
    iv = init[40:56]
    stream = _keystream(key, iv)
    plain = bytes(a ^ b for a, b in zip(init[56:64], stream[56:64]))
    proto = struct.unpack_from("<I", plain, 0)[0]
    dc_raw = struct.unpack_from("<h", plain, 4)[0]
    if proto not in PROTO_TAGS:
        return None
    dc = abs(dc_raw)
    if 1 <= dc <= 5:
        return dc, dc_raw < 0
    return None


def patch_dc(init: bytearray, dc: int, is_media: bool) -> None:
    if len(init) < 64 or not (1 <= dc <= 5):
        return
    dc_signed = -dc if is_media else dc
    new_dc = struct.pack("<h", dc_signed)
    key = bytes(init[8:40])
    iv = bytes(init[40:56])
    stream = _keystream(key, iv)
    init[60] = stream[60] ^ new_dc[0]
    init[61] = stream[61] ^ new_dc[1]


class MsgSplitter:
    """
    TCP MTProto -> отдельные WS-фреймы (по одному транспортному пакету).
    Поддержка abridged и intermediate (большие файлы).
    """

    __slots__ = ("_enc", "_proto", "_plain", "_cipher_buf", "_disabled")

    def __init__(self, init: bytes) -> None:
        key = init[8:40]
        iv = init[40:56]
        self._enc = _AesCtr(key, iv)
        self._enc.update(ZERO_64)
        self._proto = _proto_from_init(init)
        self._plain = bytearray()
        self._cipher_buf = bytearray()
        self._disabled = self._proto not in (
            PROTO_ABRIDGED,
            PROTO_INTERMEDIATE,
            PROTO_PADDED_INTERMEDIATE,
        )

    def split(self, chunk: bytes) -> list[bytes]:
        if not chunk:
            return []
        if self._disabled:
            return [chunk]

        self._cipher_buf.extend(chunk)
        self._plain.extend(self._enc.update(chunk))

        parts: list[bytes] = []
        while self._cipher_buf:
            n = self._next_packet_len()
            if n is None:
                break
            if n <= 0:
                parts.append(bytes(self._cipher_buf))
                self._plain.clear()
                self._cipher_buf.clear()
                self._disabled = True
                break
            parts.append(bytes(self._cipher_buf[:n]))
            del self._plain[:n]
            del self._cipher_buf[:n]
        return parts

    def flush(self) -> list[bytes]:
        if not self._cipher_buf:
            return []
        tail = bytes(self._cipher_buf)
        self._plain.clear()
        self._cipher_buf.clear()
        return [tail]

    def _next_packet_len(self) -> int | None:
        if not self._plain:
            return None
        if self._proto == PROTO_ABRIDGED:
            return self._abridged_len()
        if self._proto in (PROTO_INTERMEDIATE, PROTO_PADDED_INTERMEDIATE):
            return self._intermediate_len()
        return 0

    def _abridged_len(self) -> int | None:
        first = self._plain[0]
        if first in (0x7F, 0xFF):
            if len(self._plain) < 4:
                return None
            payload = int.from_bytes(self._plain[1:4], "little") * 4
            total = 4 + payload
        else:
            payload = (first & 0x7F) * 4
            total = 1 + payload
        if payload <= 0:
            return 0
        if len(self._plain) < total:
            return None
        return total

    def _intermediate_len(self) -> int | None:
        if len(self._plain) < 4:
            return None
        payload = struct.unpack_from("<I", self._plain, 0)[0] & 0x7FFFFFFF
        if payload <= 0:
            return 0
        total = 4 + payload
        if len(self._plain) < total:
            return None
        return total
