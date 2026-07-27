"""Tests for the KASE Pilot application entry point."""

import tomllib
import urllib.request
from pathlib import Path

import pytest

from kase_pilot.main import main


def test_console_script_targets_main() -> None:
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project_metadata = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert project_metadata["project"]["scripts"]["kase-pilot"] == (
        "kase_pilot.main:main"
    )


def test_main_prints_current_startup_message(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("main() must not access the network")

    monkeypatch.setattr(urllib.request, "urlopen", fail_on_network)

    main()

    assert capsys.readouterr().out.splitlines() == [
        "KASE Pilot v0.1.0",
        "System initialized successfully.",
    ]
