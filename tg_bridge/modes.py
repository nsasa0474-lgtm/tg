from __future__ import annotations

from dataclasses import dataclass

MODE_CHOICES = ("default", "pc", "socks", "vpn", "system", "all")


@dataclass(frozen=True)
class ModeFlags:
    system_proxy_enabled: bool
    use_nat: bool
    auto_tg: bool
    auto_browser: bool


def resolve_mode(mode: str) -> str:
    return mode if mode != "default" else "pc"


def build_mode_flags(
    mode: str,
    *,
    system_proxy: bool,
    nat: bool,
    no_tg_link: bool,
    no_browser: bool,
    zapret: bool,
    open_browser: bool = False,
) -> ModeFlags:
    resolved = resolve_mode(mode)
    return ModeFlags(
        system_proxy_enabled=system_proxy or resolved in ("system", "all"),
        use_nat=nat or resolved == "vpn",
        auto_tg=not no_tg_link and resolved in ("pc", "default", "all"),
        # web.telegram.org с обходом не работает — только Desktop-клиент
        auto_browser=(
            open_browser
            and not zapret
            and resolved in ("pc", "default", "all")
        ),
    )
