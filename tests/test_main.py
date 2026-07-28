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


class FakeGetCurrentQuotes:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[object] = []

    def execute(self, symbols: object) -> dict[str, Any]:
        self.calls.append(symbols)
        return self.response


class FakeFindInstrument:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[object] = []

    def execute(self, query: object) -> dict[str, Any]:
        self.calls.append(query)
        return self.response


class FakeGetHistoricalCandles:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[object] = []

    def execute(self, symbol: object) -> dict[str, Any]:
        self.calls.append(symbol)
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
        "info",
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


def test_run_routes_quotes_and_passes_single_ticker_sequence(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"quotes": {"AAPL.US": {"last": "211.16"}}}
    use_case = FakeGetCurrentQuotes(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetCurrentQuotes:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_current_quotes", fake_create)

    exit_code = main_module.run("quotes", "AAPL.US", environ={})

    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [["AAPL.US"]]
    assert capsys.readouterr() == (json.dumps(response) + "\n", "")


def test_run_routes_search_without_transforming_query(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    query = "  aPpLe Inc  "
    response = {"items": [{"ticker": "AAPL.US", "price": "211.16"}]}
    use_case = FakeFindInstrument(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeFindInstrument:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_find_instrument", fake_create)

    exit_code = main_module.run("search", query, environ={})

    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [query]
    assert use_case.calls[0] is query
    assert capsys.readouterr() == (json.dumps(response) + "\n", "")


def test_run_routes_candles_using_broker_defaults(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    symbol = " Aapl.Us "
    response = {
        "candles": [{"time": 1700000000, "open": "189.25"}],
        "unknown": {"nested": True},
    }
    use_case = FakeGetHistoricalCandles(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetHistoricalCandles:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_historical_candles", fake_create)

    exit_code = main_module.run("candles", symbol, environ={})

    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [symbol]
    assert use_case.calls[0] is symbol
    assert capsys.readouterr() == (json.dumps(response) + "\n", "")


def test_run_rejects_unknown_command() -> None:
    with pytest.raises(ValueError, match="Unknown command"):
        main_module.run("unknown", "AAPL.US")


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

    main_module.run("info", "AAPL.US", sup=False, environ={})

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
        main_module.run("info", "AAPL.US")

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
        main_module.run("info", "AAPL.US")

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
        main_module.run("info", "AAPL.US")

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
        main_module.run("info", "AAPL.US")

    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("command", ["info", "quotes", "search", "candles"])
def test_main_routes_command_and_ticker_to_run(
    command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_run(selected_command: str, ticker: str) -> int:
        calls.append((selected_command, ticker))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main([command, " Aapl.Us "]) == 17
    assert calls == [(command, " Aapl.Us ")]


def test_main_uses_process_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(sys, "argv", ["kase-pilot", "quotes", "AAPL.US"])
    monkeypatch.setattr(
        main_module,
        "run",
        lambda command, ticker: calls.append((command, ticker)) or 0,
    )

    assert main_module.main() == 0
    assert calls == [("quotes", "AAPL.US")]


def test_main_formats_configuration_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    public_key = "test-public-credential"
    private_key = "test-private-credential"
    message = "Missing required environment variable: TRADERNET_PUBLIC_KEY"

    def fail_run(command: str, ticker: str) -> None:
        calls.append((command, ticker))
        raise ConfigurationError(message)

    monkeypatch.setattr(main_module, "run", fail_run)

    exit_code = main_module.main(["search", " aPpLe Inc "])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == [("search", " aPpLe Inc ")]
    assert captured.out == ""
    assert captured.err == message + "\n"
    assert "Traceback" not in captured.err
    assert public_key not in captured.err
    assert private_key not in captured.err


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["info"],
        ["quotes"],
        ["search"],
        ["candles"],
        ["info", "AAPL.US", "extra"],
        ["search", "Apple", "extra"],
        ["candles", "AAPL.US", "extra"],
        ["foo", "AAPL.US"],
        ["AAPL.US"],
    ],
)
def test_main_rejects_invalid_argument_count(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda command, ticker: calls.append((command, ticker)) or 0,
    )

    exit_code = main_module.main(arguments)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert calls == []
    assert captured.out == ""
    assert captured.err == (
        "Usage:\n"
        "  kase-pilot info TICKER\n"
        "  kase-pilot quotes TICKER\n"
        "  kase-pilot search QUERY\n"
        "  kase-pilot candles SYMBOL\n"
    )


def test_main_propagates_run_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("run failed")

    def fail_run(command: str, ticker: str) -> None:
        raise original

    monkeypatch.setattr(main_module, "run", fail_run)

    with pytest.raises(RuntimeError) as exc_info:
        main_module.main(["info", "AAPL.US"])

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")
