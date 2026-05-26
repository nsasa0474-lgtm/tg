from __future__ import annotations

import os
import sys


def is_android() -> bool:
    if "ANDROID_ARGUMENT" in os.environ or "ANDROID_PRIVATE" in os.environ:
        return True
    if hasattr(sys, "getandroidapplicaton"):
        return True
    try:
        from java import jclass  # noqa: F401 — Chaquopy

        return True
    except Exception:
        pass
    try:
        from jnius import autoclass

        autoclass("com.chaquo.python.Python")
        return True
    except Exception:
        pass
    return False


def is_windows() -> bool:
    return sys.platform == "win32"
