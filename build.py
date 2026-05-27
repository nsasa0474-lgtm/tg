#!/usr/bin/env python3
"""
Сборка TGonPC в один файл tgonpc.exe (Windows).

Запуск:
  python build.py

Результат:
  dist/tgonpc.exe  — скопируйте на любой ПК и запустите (Python не нужен).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "tgonpc.spec"
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"
OUT_NAME = "tgonpc"


def _python() -> str:
    if VENV_PY.is_file():
        return str(VENV_PY)
    return sys.executable


def _pip_install() -> None:
    py = _python()
    print("==> Зависимости...")
    try:
        subprocess.check_call([py, "-m", "pip", "install", "-q", "-U", "pip"])
    except subprocess.CalledProcessError:
        print("    (pip upgrade пропущен — продолжаем)")
    subprocess.check_call(
        [py, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements.txt")]
    )
    subprocess.check_call(
        [py, "-m", "pip", "install", "-q", "-r", str(ROOT / "requirements-build.txt")]
    )


def _windivert_binaries() -> list[tuple[str, str]]:
    """WinDivert DLL для режима --nat (если установлен pydivert)."""
    try:
        import pydivert.windivert_dll as wd
    except ImportError:
        return []
    dll_dir = Path(wd.__file__).parent
    out = []
    for name in ("WinDivert64.dll", "WinDivert32.dll", "WinDivert.sys"):
        p = dll_dir / name
        if p.is_file():
            out.append((str(p), "pydivert/windivert_dll"))
    return out


def _data_files() -> list[tuple[str, str]]:
    """Файлы данных для onefile (WinDivert, mtproxy list)."""
    out = _windivert_binaries()
    embedded = ROOT / "tg_bridge" / "mtproxy_embedded.txt"
    if embedded.is_file():
        out.append((str(embedded), "tg_bridge"))
    return out


def _hidden_imports() -> list[str]:
    return [
        "tg_bridge",
        "tg_bridge.__main__",
        "tg_bridge.main",
        "tg_bridge.admin",
        "tg_bridge.cli",
        "tg_bridge.modes",
        "tg_bridge.runner",
        "tg_bridge.routing",
        "tg_bridge.routing.pipe",
        "tg_bridge.routing.ws_bridge",
        "tg_bridge.routing.ws_connect",
        "tg_bridge.routing.tcp_relay",
        "tg_bridge.routing.mtproxy_forward",
        "tg_bridge.routing.telegram",
        "tg_bridge.logging_setup",
        "tg_bridge.config",
        "tg_bridge.connect",
        "tg_bridge.handler",
        "tg_bridge.websocket",
        "tg_bridge.mtproto",
        "tg_bridge.ip_map",
        "tg_bridge.netutil",
        "tg_bridge.platform",
        "tg_bridge.relay_pool",
        "tg_bridge.socks5_server",
        "tg_bridge.http_proxy",
        "tg_bridge.pac_server",
        "tg_bridge.pac",
        "tg_bridge.browser_launch",
        "tg_bridge.system_proxy",
        "tg_bridge.telegram_setup",
        "tg_bridge.lifecycle",
        "tg_bridge.transparent_server",
        "tg_bridge.nat_table",
        "tg_bridge.nat_redirect",
        "tg_bridge.mtproxy_secret",
        "tg_bridge.mtproxy_client",
        "tg_bridge.mtproxy_tunnel",
        "tg_bridge.mtproxy_pool",
        "tg_bridge.mtproxy_fetch",
        "pyaes",
    ]


def _write_spec() -> None:
    datas = _data_files()
    datas_repr = repr(datas)
    hidden_repr = repr(_hidden_imports())

    spec = f'''# -*- mode: python ; coding: utf-8 -*-
# Автогенерация: python build.py

block_cipher = None

a = Analysis(
    [r'{ROOT / "run.py"}'],
    pathex=[r'{ROOT}'],
    binaries=[],
    datas={datas_repr},
    hiddenimports={hidden_repr},
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'pytest', 'pydivert.tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{OUT_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
'''
    SPEC.write_text(spec, encoding="utf-8")
    print(f"==> Spec: {SPEC}")


def _build() -> Path:
    py = _python()
    _write_spec()
    if BUILD.exists():
        shutil.rmtree(BUILD)
    print("==> PyInstaller (один .exe, 1–3 мин)...")
    subprocess.check_call(
        [
            py,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC),
        ],
        cwd=str(ROOT),
    )
    exe = DIST / f"{OUT_NAME}.exe"
    if not exe.is_file():
        raise SystemExit(f"Не найден {exe}")
    return exe


def main() -> int:
    if sys.platform != "win32":
        print("Сборка .exe только для Windows.")
        return 1

    os.chdir(ROOT)
    _pip_install()
    exe = _build()
    mb = exe.stat().st_size / (1024 * 1024)
    print()
    print("=" * 60)
    print(f"  Готово: {exe}")
    print(f"  Размер: {mb:.1f} MB")
    print()
    print("  На другом ПК: скопируйте tgonpc.exe и запустите.")
    print("  В Telegram нажмите «Подключить», если спросит прокси.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
