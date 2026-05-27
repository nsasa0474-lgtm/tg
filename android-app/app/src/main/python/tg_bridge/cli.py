from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from tg_bridge.config import BridgeConfig, DEFAULT_RELAY_IP
from tg_bridge.lifecycle import RuntimeState
from tg_bridge.logging_setup import setup_logging
from tg_bridge.modes import MODE_CHOICES, build_mode_flags, resolve_mode

log = logging.getLogger("tg_bridge")


@dataclass
class ParsedArgs:
    namespace: argparse.Namespace
    log_path: Path
    mode: str
    cfg: BridgeConfig
    state: RuntimeState


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TGonPC")
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
        choices=list(MODE_CHOICES),
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
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Путь к файлу лога (по умолчанию logs/tgonpc.log рядом с run.py)",
    )
    return parser


def parse_cli(argv: list[str]) -> ParsedArgs:
    args = build_parser().parse_args(argv[1:])

    log_path = setup_logging(verbose=args.verbose, log_file=args.log_file)
    if not args.verbose:
        logging.getLogger("asyncio").setLevel(logging.CRITICAL)

    mode = resolve_mode(args.mode)
    bind_host = "0.0.0.0" if args.lan else args.host

    cfg = BridgeConfig(
        host=bind_host,
        port=args.port,
        http_port=args.http_port,
        pac_port=args.pac_port,
        dc_relay_ips={i: args.relay_ip for i in range(1, 6)},
    )

    if args.zapret:
        args.no_browser = True

    flags = build_mode_flags(
        args.mode,
        system_proxy=args.system_proxy,
        nat=args.nat,
        no_tg_link=args.no_tg_link,
        no_browser=args.no_browser,
        zapret=args.zapret,
    )

    state = RuntimeState(
        cfg=cfg,
        system_proxy_enabled=flags.system_proxy_enabled,
        use_nat=flags.use_nat,
        auto_tg=flags.auto_tg,
        auto_browser=flags.auto_browser,
    )

    return ParsedArgs(
        namespace=args,
        log_path=log_path,
        mode=mode,
        cfg=cfg,
        state=state,
    )


def print_banner(parsed: ParsedArgs) -> None:
    args = parsed.namespace
    cfg = parsed.cfg
    state = parsed.state

    print()
    print("=" * 62)
    print("  TGonPC")
    print("=" * 62)
    print(f"  SOCKS5:   {cfg.host}:{cfg.port}")
    if args.lan:
        print("  Режим LAN: телефон -> SOCKS5 IP_этого_ПК:1080 (см. README)")
    print(f"  Сист.пр.: {'да' if state.system_proxy_enabled else 'нет (не мешает Запрету)'}")
    print(f"  Лог:      {parsed.log_path}")
    print("             (при ошибке можно сказать «смотри лог» — не копировать консоль)")
    print()
    if state.auto_tg:
        print("  Telegram: нажмите «Подключить» в приложении")
    print("  Закройте окно или Ctrl+C — всё сбросится автоматически")
    print("=" * 62)
    print()
