from __future__ import annotations

import argparse
import asyncio
import ctypes
import logging
import sys

from tg_bridge.browser_launch import open_web_telegram
from tg_bridge.config import BridgeConfig, DEFAULT_RELAY_IP
from tg_bridge.http_proxy import run_http_server
from tg_bridge.lifecycle import (
    RuntimeState,
    apply_frozen_exe_defaults,
    async_shutdown,
    bind_state,
    full_shutdown,
    recover_stale_proxy,
    register_exit_hooks,
)
from tg_bridge.netutil import install_quiet_asyncio_handler, wait_socks5_ready
from tg_bridge.pac_server import run_pac_server
from tg_bridge.socks5_server import run_server
from tg_bridge.system_proxy import SystemProxy
from tg_bridge.telegram_setup import apply_telegram_proxy


def _is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _request_admin_rerun() -> bool:
    if _is_admin():
        return False
    try:
        script = sys.argv[0]
        params = " ".join(f'"{a}"' if " " in a else a for a in sys.argv[1:])
        cmd = f'"{script}" {params}'.strip()
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, cmd, None, 1)
        return True
    except Exception:
        return False


async def _run_services(state: RuntimeState) -> None:
    cfg = state.cfg
    install_quiet_asyncio_handler()

    state.tasks = [
        asyncio.create_task(run_server(cfg, state), name="socks5"),
        asyncio.create_task(run_http_server(cfg, state), name="http"),
        asyncio.create_task(run_pac_server(cfg, state), name="pac"),
    ]

    if state.use_nat and _is_admin():
        from tg_bridge.nat_redirect import start_nat_thread
        from tg_bridge.transparent_server import run_transparent_server

        start_nat_thread()
        state.tasks.append(
            asyncio.create_task(run_transparent_server(cfg, state), name="nat")
        )

    await wait_socks5_ready(cfg.host, cfg.port)

    if state.system_proxy_enabled:
        state.proxy_ctx = SystemProxy(cfg.host, cfg.port, cfg.http_port, cfg.pac_port)
        state.proxy_ctx.enable()

    if state.auto_tg:
        apply_telegram_proxy(cfg.host, cfg.port)

    if state.auto_browser:
        open_web_telegram(cfg.host, cfg.http_port)

    try:
        await asyncio.gather(*state.tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await async_shutdown(state)


def main(argv: list[str] | None = None) -> int:
    argv = apply_frozen_exe_defaults(sys.argv if argv is None else argv)

    parser = argparse.ArgumentParser(description="TG Tunnel")
    parser.add_argument("--host", default="127.0.0.1", help="127.0.0.1 или 0.0.0.0 для телефона в Wi‑Fi")
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Слушать на всех интерфейсах (0.0.0.0) — Telegram на телефоне в той же сети",
    )
    parser.add_argument("-p", "--port", type=int, default=1080)
    parser.add_argument("--http-port", type=int, default=1081)
    parser.add_argument("--pac-port", type=int, default=1082)
    parser.add_argument("--relay-ip", default=DEFAULT_RELAY_IP)
    parser.add_argument(
        "--mode",
        choices=["default", "pc", "socks", "vpn", "system", "all"],
        default="default",
    )
    parser.add_argument("--no-uac", action="store_true")
    parser.add_argument("--no-tg-link", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--system-proxy",
        action="store_true",
        help="Системный прокси Windows (не использовать с «Запрет»)",
    )
    parser.add_argument("--zapret", action="store_true", help="= --no-browser, без сист. прокси")
    parser.add_argument("--nat", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv[1:])

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    if not args.verbose:
        logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    mode = args.mode if args.mode != "default" else "pc"

    bind_host = "0.0.0.0" if args.lan else args.host

    cfg = BridgeConfig(
        host=bind_host,
        port=args.port,
        http_port=args.http_port,
        pac_port=args.pac_port,
        dc_relay_ips={i: args.relay_ip for i in range(1, 6)},
    )

    use_nat = args.nat or mode == "vpn"
    if use_nat and not _is_admin() and not args.no_uac:
        print("\n  Запрос прав администратора (для NAT)...\n")
        if _request_admin_rerun():
            return 0

    if args.zapret:
        args.no_browser = True

    state = RuntimeState(
        cfg=cfg,
        system_proxy_enabled=args.system_proxy or mode in ("system", "all"),
        use_nat=use_nat,
        auto_tg=not args.no_tg_link and mode in ("pc", "default", "all"),
        auto_browser=(
            not args.no_browser
            and not args.zapret
            and mode in ("pc", "default", "all")
        ),
    )

    bind_state(state)
    register_exit_hooks(cfg)
    recover_stale_proxy(cfg)

    print()
    print("=" * 62)
    print("  TG Tunnel")
    print("=" * 62)
    print(f"  SOCKS5:   {cfg.host}:{cfg.port}")
    if args.lan:
        print("  Режим LAN: телефон -> SOCKS5 IP_этого_ПК:1080 (см. README)")
    print(f"  Сист.пр.: {'да' if state.system_proxy_enabled else 'нет (не мешает Запрету)'}")
    print()
    if state.auto_tg:
        print("  Telegram: нажмите «Подключить» в приложении")
    print("  Закройте окно или Ctrl+C — всё сбросится автоматически")
    print("=" * 62)
    print()

    try:
        asyncio.run(_run_services(state))
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        full_shutdown(cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
