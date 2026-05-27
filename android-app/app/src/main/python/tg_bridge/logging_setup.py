from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Между INFO и WARNING — только для консоли (файл пишет полный DEBUG+INFO).
CONSOLE = 25
logging.addLevelName(CONSOLE, "CONSOLE")


def default_log_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "logs" / "tgonpc.log"


def _install_status_method() -> None:
    if hasattr(logging.Logger, "status"):
        return

    def status(self: logging.Logger, msg: object, *args: object, **kwargs: object) -> None:
        if self.isEnabledFor(CONSOLE):
            self._log(CONSOLE, msg, args, **kwargs)

    logging.Logger.status = status  # type: ignore[method-assign]


def setup_logging(
    *,
    verbose: bool = False,
    log_file: Path | None = None,
) -> Path:
    """Консоль — минимум (status + warnings); файл — полный DEBUG с ротацией."""
    _install_status_method()

    path = (log_file or default_log_path()).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    console_fmt = logging.Formatter(
        "%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )
    file_fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else CONSOLE)
    console.setFormatter(console_fmt)
    root.addHandler(console)

    fh = RotatingFileHandler(
        path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)
    root.addHandler(fh)

    return path
