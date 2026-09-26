"""Logging setup: rich console + a plain-text run.log per job."""

from __future__ import annotations

import logging
from pathlib import Path

from rich.logging import RichHandler

_CONSOLE_CONFIGURED = False


def get_logger(name: str = "echoface") -> logging.Logger:
    global _CONSOLE_CONFIGURED
    logger = logging.getLogger(name)
    if not _CONSOLE_CONFIGURED:
        root = logging.getLogger("echoface")
        root.setLevel(logging.INFO)
        handler = RichHandler(rich_tracebacks=True, show_path=False, markup=False)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        root.addHandler(handler)
        _CONSOLE_CONFIGURED = True
    return logger


def attach_job_log_file(logger: logging.Logger, run_log_path: Path) -> logging.Handler:
    """Attach a plain-text file handler (output/<job>/run.log) to the logger.

    Returns the handler so the caller can remove it when the job finishes.
    """
    run_log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(run_log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(file_handler)
    return file_handler


def detach_handler(logger: logging.Logger, handler: logging.Handler) -> None:
    try:
        handler.close()
    finally:
        logger.removeHandler(handler)
