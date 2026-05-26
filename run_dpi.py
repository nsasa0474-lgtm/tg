"""Старый режим WinDivert (только если probe показывает OK к DC)."""
from tg_dpi.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["start", "--strategy", "aggressive", "--debug"]))
