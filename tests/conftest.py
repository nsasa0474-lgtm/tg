"""Shared helpers for tg_bridge tests."""

from __future__ import annotations

import os
import struct

from tg_bridge.mtproto import PROTO_ABRIDGED, _AesCtr


def make_mtproto_init(dc: int, *, is_media: bool = False, proto: int = PROTO_ABRIDGED) -> bytes:
    init = bytearray(os.urandom(64))
    key = bytes(init[8:40])
    iv = bytes(init[40:56])
    stream = _AesCtr(key, iv).keystream(64)
    dc_signed = -dc if is_media else dc
    plain = struct.pack("<I", proto) + struct.pack("<h", dc_signed) + b"\x00\x00"
    init[56:64] = bytes(a ^ b for a, b in zip(plain, stream[56:64]))
    return bytes(init)
