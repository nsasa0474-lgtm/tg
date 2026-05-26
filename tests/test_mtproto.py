from __future__ import annotations

from tg_bridge import mtproto
from tg_bridge.mtproto import PROTO_ABRIDGED, MsgSplitter

from tests.conftest import make_mtproto_init


def test_extract_dc_round_trip() -> None:
    init = make_mtproto_init(3, is_media=False)
    assert mtproto.extract_dc(init) == (3, False)


def test_extract_dc_media() -> None:
    init = make_mtproto_init(4, is_media=True)
    assert mtproto.extract_dc(init) == (4, True)


def test_patch_dc_changes_dc() -> None:
    init = bytearray(make_mtproto_init(1))
    mtproto.patch_dc(init, 5, False)
    assert mtproto.extract_dc(bytes(init)) == (5, False)


def test_msg_splitter_abridged_waits_for_full_packet() -> None:
    init = make_mtproto_init(2, proto=PROTO_ABRIDGED)
    splitter = MsgSplitter(init)
    partial = b"\x02"
    assert splitter.split(partial) == []
    assert splitter.flush() == [partial]


def test_msg_splitter_disabled_for_unknown_proto() -> None:
    init = make_mtproto_init(2, proto=0x12345678)
    splitter = MsgSplitter(init)
    chunk = b"whole-chunk"
    assert splitter.split(chunk) == [chunk]
