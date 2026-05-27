from __future__ import annotations

import base64
import re

_HEX = re.compile(r"^[0-9a-fA-F]+$")


def _b64_payload(payload: str) -> bytes:
    pad = "=" * ((4 - len(payload) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(payload + pad)
    except Exception:
        return base64.b64decode(payload + pad)


def _decode_payload(payload: str) -> bytes:
    if _HEX.match(payload) and len(payload) % 2 == 0:
        try:
            return bytes.fromhex(payload)
        except ValueError:
            pass
    return _b64_payload(payload)


def parse_mtproxy_secret(secret: str) -> bytes:
    s = secret.strip().replace("-", "")
    if s.startswith(("ee", "dd")):
        return _decode_payload(s[2:])
    if len(s) == 32 and _HEX.match(s):
        return bytes.fromhex(s)
    if _HEX.match(s) and len(s) % 2 == 0:
        return bytes.fromhex(s)
    return _b64_payload(s)
