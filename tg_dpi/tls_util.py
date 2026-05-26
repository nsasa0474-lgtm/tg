from __future__ import annotations

# TLS record: content_type(1) + version(2) + length(2)
_TLS_HANDSHAKE = 0x16


def is_tls_client_hello(payload: bytes) -> bool:
    return (
        len(payload) >= 6
        and payload[0] == _TLS_HANDSHAKE
        and payload[1] == 0x03
        and payload[5] == 0x01
    )


def find_sni_hostname(payload: bytes) -> str | None:
    """
    Извлечь SNI из TLS ClientHello (упрощённый парсер).
    Возвращает hostname или None.
    """
    if not is_tls_client_hello(payload):
        return None
    try:
        # пропускаем TLS record + handshake header
        i = 5 + 4 + 2 + 32  # record(5) + hs_type(1)+len(3) + ver(2) + random(32)
        if i >= len(payload):
            return None
        i += 1 + payload[i]  # session id
        if i + 2 > len(payload):
            return None
        cs_len = int.from_bytes(payload[i : i + 2], "big")
        i += 2 + cs_len
        if i >= len(payload):
            return None
        i += 1 + payload[i]  # compression
        if i + 2 > len(payload):
            return None
        ext_len = int.from_bytes(payload[i : i + 2], "big")
        i += 2
        end = i + ext_len
        while i + 4 <= end and i + 4 <= len(payload):
            etype = int.from_bytes(payload[i : i + 2], "big")
            elen = int.from_bytes(payload[i + 2 : i + 4], "big")
            i += 4
            if i + elen > len(payload):
                break
            if etype == 0x0000:  # server_name
                data = payload[i : i + elen]
                if len(data) >= 5 and data[2] == 0x00:  # host_name
                    nlen = int.from_bytes(data[3:5], "big")
                    if len(data) >= 5 + nlen:
                        return data[5 : 5 + nlen].decode("ascii", errors="ignore")
            i += elen
    except (IndexError, ValueError):
        return None
    return None


def split_at_sni(payload: bytes, default: int = 2) -> int:
    """Разрез прямо перед SNI в ClientHello — эффективно против DPI по TLS."""
    marker = b"\x00\x00"  # тип extension server_name часто после других полей
    sni = find_sni_hostname(payload)
    if sni:
        host_bytes = sni.encode("ascii")
        pos = payload.find(host_bytes)
        if pos > 1:
            return pos
    # fallback: после типичного заголовка ClientHello
    if is_tls_client_hello(payload) and len(payload) > 40:
        return min(39, len(payload) - 1)
    return default
