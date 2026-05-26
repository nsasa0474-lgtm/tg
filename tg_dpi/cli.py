from __future__ import annotations

import argparse
import ctypes
import logging
import socket
import sys
from pathlib import Path

from tg_dpi import __version__
from tg_dpi.diagnose import run_network_diagnose, summarize
from tg_dpi.engine import DpiEngine
from tg_dpi.strategies import (
    AggressiveStrategy,
    ComboStrategy,
    DcStrategy,
    FakeStrategy,
    PassiveStrategy,
    SplitStrategy,
)
from tg_dpi.strategies.base import Strategy
from tg_dpi.traffic import TrafficClassifier

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CIDR = ROOT / "lists" / "telegram_cidr.txt"
DEFAULT_HOSTS = ROOT / "lists" / "telegram_hosts.txt"
DEFAULT_DC_IPS = ROOT / "lists" / "telegram_dc_ips.txt"

STRATEGIES = ("aggressive", "dc", "combo", "passive", "split", "fake")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def build_strategy(name: str, split_at: int, fake_ttl: int) -> Strategy:
    if name == "aggressive":
        return AggressiveStrategy(fake_ttl=fake_ttl)
    if name == "dc":
        return DcStrategy(fake_ttl=fake_ttl)
    if name == "split":
        return SplitStrategy(split_at=split_at, reverse=False, auto_sni=False)
    if name == "fake":
        return FakeStrategy(fake_ttl=fake_ttl)
    if name == "combo":
        return ComboStrategy(split_at=split_at, fake_ttl=fake_ttl)
    return PassiveStrategy()


def cmd_probe(_: argparse.Namespace) -> int:
    print(f"tg_dpi probe v{__version__}\n")
    results = run_network_diagnose()
    for r in results:
        mark = "OK  " if r.ok else "FAIL"
        print(f"  {mark} {r.name:16} {r.host} — {r.detail}")
    print()
    print(summarize(results)[0])
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    if not is_admin():
        print("Ошибка: нужны права администратора.")
        print("Запустите IDE от имени администратора.")
        return 1

    classifier = TrafficClassifier.from_files(
        Path(args.cidr),
        Path(args.hosts),
        Path(args.dc_ips),
    )
    strategy = build_strategy(args.strategy, args.split_at, args.fake_ttl)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"tg_dpi v{__version__}")
    print(f"  Стратегия: {strategy.name}")
    print(f"  DC IP:     {len(classifier.dc_ips)} шт.")
    print()
    print("  1) Закройте Telegram полностью")
    print("  2) Run на run.py (админ)")
    print("  3) Откройте Telegram")
    print()
    print("  В логе ищите SEE/MOD к 149.154.* или 91.108.*")
    print("  Если SEE нет — сначала: python -m tg_dpi probe")
    print()

    try:
        DpiEngine(strategy, classifier, debug=args.debug).run()
    except KeyboardInterrupt:
        print("\nОстановлено.")
        return 0
    except OSError as exc:
        print(f"WinDivert: {exc}")
        return 1
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    print(f"tg_dpi v{__version__}")
    print(f"  Python:  {sys.version.split()[0]}")
    print(f"  Админ:   {'да' if is_admin() else 'НЕТ'}")
    try:
        import pydivert  # noqa: F401

        print("  pydivert: OK")
    except ImportError:
        print("  pydivert: не установлен")
        return 1
    if DEFAULT_CIDR.is_file():
        c = TrafficClassifier.from_files(DEFAULT_CIDR, DEFAULT_HOSTS, DEFAULT_DC_IPS)
        print(f"  DC IP:   {len(c.dc_ips)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Обход DPI для Telegram (Windows)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start")
    start.add_argument("--strategy", choices=STRATEGIES, default="aggressive")
    start.add_argument("--split-at", type=int, default=2)
    start.add_argument("--fake-ttl", type=int, default=4)
    start.add_argument("--cidr", type=Path, default=DEFAULT_CIDR)
    start.add_argument("--hosts", type=Path, default=DEFAULT_HOSTS)
    start.add_argument("--dc-ips", type=Path, default=DEFAULT_DC_IPS)
    start.add_argument("--debug", action="store_true")
    start.add_argument("-v", "--verbose", action="store_true")
    start.set_defaults(func=cmd_start)

    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("probe").set_defaults(func=cmd_probe)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
