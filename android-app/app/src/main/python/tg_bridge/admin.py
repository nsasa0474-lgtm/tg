from __future__ import annotations

import ctypes
import sys


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def request_admin_rerun() -> bool:
    if is_admin():
        return False
    try:
        script = sys.argv[0]
        params = " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])
        cmd = f'"{script}" {params}'.strip()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd, None, 1)
        return True
    except Exception:
        return False
