from __future__ import annotations

import asyncio
import logging

from tg_bridge.admin import is_admin
from tg_bridge.browser_launch import open_web_telegram
from tg_bridge.http_proxy import run_http_server
from tg_bridge.lifecycle import RuntimeState, async_shutdown
from tg_bridge.netutil import install_quiet_asyncio_handler, wait_exit_ready, wait_socks5_ready
from tg_bridge.pac_server import run_pac_server
from tg_bridge.relay_pool import get_probe_progress, kick_exit_probe
from tg_bridge.socks5_server import run_server
from tg_bridge.system_proxy import SystemProxy
from tg_bridge.telegram_setup import apply_telegram_proxy

log = logging.getLogger("tg_bridge")


async def relay_watchdog() -> None:
    while True:
        await asyncio.sleep(90)
        try:
            from tg_bridge.relay_pool import health_check_relay

            await health_check_relay()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.debug("relay watchdog: %s", exc)


async def run_services(state: RuntimeState) -> None:
    cfg = state.cfg
    install_quiet_asyncio_handler()

    state.tasks = [
        asyncio.create_task(run_server(cfg, state), name="socks5"),
        asyncio.create_task(run_http_server(cfg, state), name="http"),
        asyncio.create_task(run_pac_server(cfg, state), name="pac"),
        asyncio.create_task(relay_watchdog(), name="relay-watchdog"),
    ]

    if state.use_nat and is_admin():
        from tg_bridge.nat_redirect import start_nat_thread
        from tg_bridge.transparent_server import run_transparent_server

        start_nat_thread()
        state.tasks.append(
            asyncio.create_task(run_transparent_server(cfg, state), name="nat")
        )

    await wait_socks5_ready(cfg.host, cfg.port)
    kick_exit_probe()

    exit_ok = await wait_exit_ready(55.0)
    if not exit_ok:
        prog = get_probe_progress()
        print(f"  Внимание: выход ещё не найден ({prog or 'поиск…'})")
        print("  Подождите строку «Выход готов» в логе, затем включите прокси в Telegram.")
        print()

    if state.system_proxy_enabled:
        state.proxy_ctx = SystemProxy(cfg.host, cfg.port, cfg.http_port, cfg.pac_port)
        state.proxy_ctx.enable()

    if state.auto_tg:
        if exit_ok:
            apply_telegram_proxy(cfg.host, cfg.port)
        else:
            print(
                f"  Telegram: укажите SOCKS5 {cfg.host}:{cfg.port} вручную "
                "после «Выход готов» в логе"
            )

    if state.auto_browser:
        open_web_telegram(cfg.host, cfg.http_port)

    try:
        await asyncio.gather(*state.tasks)
    except asyncio.CancelledError:
        pass
    finally:
        await async_shutdown(state)
