"""Tests for the KASE Pilot application entry point."""

import json
import sys
import tomllib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import kase_pilot.main as main_module
from kase_pilot.core.exceptions import ConfigurationError


def test_console_script_targets_main() -> None:
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project_metadata = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert project_metadata["project"]["scripts"]["kase-pilot"] == (
        "kase_pilot.main:main"
    )


class FakeGetSecurityInfo:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls: list[tuple[str, bool]] = []

    def execute(self, ticker: str, *, sup: bool = True) -> dict[str, Any]:
        self.calls.append((ticker, sup))
        if self.error is not None:
            raise self.error
        return self.response


def test_run_orchestrates_use_case_and_prints_only_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    environment = {
        "TRADERNET_PUBLIC_KEY": "PublicKey",
        "TRADERNET_PRIVATE_KEY": "PrivateKey",
    }
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "nt_ticker": "AAPL.US",
        "min_step": "0.01",
        "lot": "1",
        "unknown": {"nested": [True, None]},
    }
    use_case = FakeGetSecurityInfo(response)
    load_calls: list[tuple[Path | None, object]] = []
    composition_calls: list[tuple[str, str]] = []

    def fake_load_settings(
        project_root: Path | None = None,
        *,
        environ: object = None,
    ) -> SimpleNamespace:
        load_calls.append((project_root, environ))
        return settings

    def fake_create(public_key: str, private_key: str) -> FakeGetSecurityInfo:
        composition_calls.append((public_key, private_key))
        return use_case

    monkeypatch.setattr(main_module, "load_settings", fake_load_settings)
    monkeypatch.setattr(main_module, "create_get_security_info", fake_create)

    exit_code = main_module.run(
        " Aapl.Us ",
        project_root=tmp_path,
        environ=environment,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert load_calls == [(tmp_path, environment)]
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [(" Aapl.Us ", True)]
    assert captured.out == json.dumps(response) + "\n"
    assert captured.err == ""
    assert "System initialized successfully." not in captured.out
    assert "PrivateKey" not in captured.out


def test_run_passes_false_sup(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="public",
        tradernet_private_key="private",
    )
    use_case = FakeGetSecurityInfo()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_security_info",
        lambda public, private: use_case,
    )

    main_module.run("AAPL.US", sup=False, environ={})

    assert use_case.calls == [("AAPL.US", False)]


def test_run_propagates_configuration_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = ConfigurationError(
        "Missing required environment variable: TRADERNET_PUBLIC_KEY"
    )

    def fail_load(*args: object, **kwargs: object) -> None:
        raise original

    monkeypatch.setattr(main_module, "load_settings", fail_load)

    with pytest.raises(ConfigurationError) as exc_info:
        main_module.run("AAPL.US")

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_run_propagates_composition_error_without_leaking_credentials(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = "private-secret"
    original = RuntimeError("composition failed")
    settings = SimpleNamespace(
        tradernet_public_key="public",
        tradernet_private_key=private_key,
    )
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fail_create(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(main_module, "create_get_security_info", fail_create)

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("AAPL.US")

    captured = capsys.readouterr()
    assert exc_info.value is original
    assert private_key not in captured.out
    assert private_key not in captured.err


def test_run_propagates_use_case_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("request failed")
    settings = SimpleNamespace(
        tradernet_public_key="public",
        tradernet_private_key="private",
    )
    use_case = FakeGetSecurityInfo(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_security_info",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("AAPL.US")

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_run_propagates_json_serialization_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="public",
        tradernet_private_key="private",
    )
    use_case = FakeGetSecurityInfo({"not_json": object()})
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_security_info",
        lambda public, private: use_case,
    )

    with pytest.raises(TypeError):
        main_module.run("AAPL.US")

    assert capsys.readouterr() == ("", "")


def test_main_passes_one_ticker_to_run(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def fake_run(ticker: str) -> int:
        calls.append(ticker)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main([" Aapl.Us "]) == 17
    assert calls == [" Aapl.Us "]


def test_main_uses_process_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sys, "argv", ["kase-pilot", "AAPL.US"])
    monkeypatch.setattr(
        main_module,
        "run",
        lambda ticker: calls.append(ticker) or 0,
    )

    assert main_module.main() == 0
    assert calls == ["AAPL.US"]


@pytest.mark.parametrize("arguments", [[], ["AAPL.US", "extra"]])
def test_main_rejects_invalid_argument_count(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda ticker: calls.append(ticker) or 0,
    )

    exit_code = main_module.main(arguments)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert calls == []
    assert captured.out == ""
    assert captured.err == "Usage: kase-pilot TICKER\n"


def test_main_propagates_run_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original = RuntimeError("run failed")

    def fail_run(ticker: str) -> None:
        raise original

    monkeypatch.setattr(main_module, "run", fail_run)

    with pytest.raises(RuntimeError) as exc_info:
        main_module.main(["AAPL.US"])

    assert exc_info.value is original
