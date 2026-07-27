"""Unit tests for explicit logger configuration."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path

import kase_pilot.core.logger as logger_module


def _close_handlers(logger: logging.Logger) -> None:
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()


def test_logger_module_import_does_not_create_settings() -> None:
    reloaded = importlib.reload(logger_module)

    assert not hasattr(reloaded, "settings")


def test_get_logger_uses_explicit_log_directory(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    logger = logger_module.get_logger("test-explicit-log-dir", log_dir)

    try:
        logger.info("message")

        assert log_dir.is_dir()
        assert (log_dir / "kase_pilot.log").is_file()
        assert len(logger.handlers) == 2
        assert all(handler.formatter is not None for handler in logger.handlers)
    finally:
        _close_handlers(logger)


def test_importing_logger_does_not_create_log_directory(tmp_path: Path) -> None:
    log_dir = tmp_path / "not-created"

    importlib.reload(logger_module)

    assert not log_dir.exists()
