from __future__ import annotations

import asyncio
import sys

from tg_bridge.admin import request_admin_rerun
from tg_bridge.cli import parse_cli, print_banner
from tg_bridge.lifecycle import (
    apply_frozen_exe_defaults,
    bind_state,
    full_shutdown,
    recover_stale_proxy,
    register_exit_hooks,
)
from tg_bridge.runner import run_services


def main(argv: list[str] | None = None) -> int:
    argv = apply_frozen_exe_defaults(sys.argv if argv is None else argv)
    parsed = parse_cli(argv)

    if parsed.state.use_nat and not parsed.namespace.no_uac:
        from tg_bridge.admin import is_admin

        if not is_admin():
            print("\n  Запрос прав администратора (для NAT)...\n")
            if request_admin_rerun():
                return 0

    bind_state(parsed.state)
    register_exit_hooks(parsed.cfg)
    recover_stale_proxy(parsed.cfg)
    print_banner(parsed)

    try:
        asyncio.run(run_services(parsed.state))
    except KeyboardInterrupt:
        print("\nОстановлено.")
    finally:
        full_shutdown(parsed.cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
