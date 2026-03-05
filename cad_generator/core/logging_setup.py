"""
Logging configuration for py-param-cad (Semana 13).

Sets up a rotating file handler (max 1 MB, 3 backups) plus a console
handler (WARNING level only to avoid polluting the terminal).

Call setup_logging() once at application startup, before any other
imports that might emit log records.
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


_LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_MAX_BYTES   = 1_000_000   # 1 MB per log file
_BACKUP_COUNT = 3


def setup_logging(log_dir: Path, level: int = logging.DEBUG) -> None:
    """
    Configure root logger with:
      - RotatingFileHandler → <log_dir>/cad_generator.log  (DEBUG+)
      - StreamHandler        → stderr                        (WARNING+)

    Safe to call multiple times; subsequent calls are no-ops if handlers
    are already attached.
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers if called more than once
    if root.handlers:
        return

    root.setLevel(level)
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Rotating file handler
    log_file = log_dir / "cad_generator.log"
    fh = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # Console handler (warnings and above only)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    logging.getLogger(__name__).debug("Logging initialized → %s", log_file)
