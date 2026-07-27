"""Logging configuration for KASE Pilot project."""

import logging
from pathlib import Path

_FORMATTER: logging.Formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str, log_dir: Path) -> logging.Logger:
    """Return a named logger with console and file handlers.

    If the logger already has handlers attached, returns it as-is to
    prevent duplicate log records on repeated calls.

    Args:
        name: Logical name for the logger (e.g. ``"broker"``).
        log_dir: Directory in which the application log file is stored.

    Returns:
        Configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_dir.mkdir(parents=True, exist_ok=True)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(_FORMATTER)

    file_handler = logging.FileHandler(log_dir / "kase_pilot.log", encoding="utf-8")
    file_handler.setFormatter(_FORMATTER)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    return logger
