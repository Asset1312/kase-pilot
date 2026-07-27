"""Tests for the KASE Pilot application entry point."""

import tomllib
import urllib.request
from pathlib import Path

import pytest

import kase_pilot.main as main_module


def test_console_script_targets_main() -> None:
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project_metadata = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert project_metadata["project"]["scripts"]["kase-pilot"] == (
        "kase_pilot.main:main"
    )


def test_run_prints_current_startup_message(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("run() must not access the network")

    monkeypatch.setattr(urllib.request, "urlopen", fail_on_network)

    exit_code = main_module.run()

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == [
        "KASE Pilot v0.1.0",
        "System initialized successfully.",
    ]


def test_main_delegates_to_run_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_run() -> int:
        nonlocal calls
        calls += 1
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main() == 17
    assert calls == 1
