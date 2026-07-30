"""Tests for the KASE Pilot application entry point."""

import copy
import json
import sys
import tomllib
from datetime import date, datetime, time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import kase_pilot.main as main_module
from kase_pilot.core.exceptions import ConfigurationError
from kase_pilot.core.version import __version__


def test_console_script_targets_main() -> None:
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    project_metadata = tomllib.loads(project_file.read_text(encoding="utf-8"))

    assert project_metadata["project"]["scripts"]["kase-pilot"] == (
        "kase_pilot.main:main"
    )


@pytest.mark.parametrize("arguments", [["--help"], ["-h"]])
def test_main_help_prints_usage_without_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda *args, **kwargs: calls.append("factory"),
    )
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: calls.append("run"),
    )

    assert main_module.main(arguments) == 0
    assert capsys.readouterr() == (main_module._USAGE + "\n", "")
    assert calls == []


def test_main_version_prints_exact_version_without_orchestration(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda *args, **kwargs: calls.append("factory"),
    )
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: calls.append("run"),
    )

    assert main_module.main(["--version"]) == 0
    assert capsys.readouterr() == (__version__ + "\n", "")
    assert calls == []


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


class FakeGetSymbols:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[dict[str, object]] = []

    def execute(self, **arguments: object) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


class FakeGetNews:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[tuple[object, object, object, object]] = []

    def execute(
        self,
        query: object,
        *,
        symbol: object = None,
        story_id: object = None,
        limit: object = 30,
    ) -> dict[str, Any]:
        self.calls.append((query, symbol, story_id, limit))
        return self.response


class FakeGetMarketStatus:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[tuple[object, object]] = []

    def execute(
        self,
        market: object = "*",
        *,
        mode: object = None,
    ) -> dict[str, Any]:
        self.calls.append((market, mode))
        return self.response


class FakeGetMostTraded:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[tuple[object, object, object, object]] = []

    def execute(
        self,
        instrument_type: object = "stocks",
        *,
        exchange: object = "usa",
        gainers: object = True,
        limit: object = 10,
    ) -> dict[str, Any]:
        self.calls.append((instrument_type, exchange, gainers, limit))
        return self.response


class FakeGetHistorical:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[dict[str, object]] = []

    def execute(self, **arguments: object) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


class FakeGetCorporateActions:
    def __init__(self, response: list[dict[str, Any]] | None = None) -> None:
        self.response = [] if response is None else response
        self.calls: list[object] = []

    def execute(self, reception: object = 35) -> list[dict[str, Any]]:
        self.calls.append(reception)
        return self.response


class FakeGetPriceAlerts:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[dict[str, object]] = []

    def execute(self, **arguments: object) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


class FakeGetRequestsHistory:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[dict[str, object]] = []

    def execute(self, **arguments: object) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


class FakeGetBrokerReport:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[dict[str, object]] = []

    def execute(self, **arguments: object) -> dict[str, Any]:
        self.calls.append(arguments)
        return self.response


class FakeGetHistoricalCandles:
    def __init__(self, response: dict[str, Any] | None = None) -> None:
        self.response = {} if response is None else response
        self.calls: list[tuple[object, dict[str, object]]] = []

    def execute(self, symbol: object, **kwargs: object) -> dict[str, Any]:
        self.calls.append((symbol, kwargs))
        return self.response


class FakeGetUserInfo:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls = 0

    def execute(self) -> dict[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeGetAccountSummary:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls = 0

    def execute(self) -> dict[str, Any]:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeGetPlacedOrders:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls: list[bool] = []

    def execute(self, active: bool = True) -> dict[str, Any]:
        self.calls.append(active)
        if self.error is not None:
            raise self.error
        return self.response


class FakeGetTradesHistory:
    def __init__(
        self,
        response: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = {} if response is None else response
        self.error = error
        self.calls: list[tuple[object, object, object, object]] = []

    def execute(
        self,
        start: object,
        end: object,
        *,
        symbol: object = None,
        limit: object = None,
    ) -> dict[str, Any]:
        self.calls.append((start, end, symbol, limit))
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
        "short_name": "Apple — акция",
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
    expected_output = json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert exit_code == 0
    assert load_calls == [(tmp_path, environment)]
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [(" Aapl.Us ", True)]
    assert captured.out == expected_output
    assert "\n  " in captured.out
    assert "Apple — акция" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
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
    response = {
        "quotes": {"AAPL.US": {"last": "211.16", "market": "США"}},
    }
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
    assert capsys.readouterr() == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


def test_run_routes_search_without_transforming_query(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    query = "  aPpLe Inc  "
    response = {
        "items": [
            {"ticker": "AAPL.US", "price": "211.16", "name": "Акция Apple"},
        ],
    }
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
    assert capsys.readouterr() == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


@pytest.mark.parametrize(
    ("exchange", "expected_arguments"),
    [(None, {}), (" KASE ", {"exchange": " KASE "})],
)
def test_run_symbols_forwards_exchange_and_prints_raw_pretty_json(
    exchange: str | None,
    expected_arguments: dict[str, object],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"result": {"symbols": [{"ticker": "HSBK.KZ", "name": "Халық"}]}}
    use_case = FakeGetSymbols(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetSymbols:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_symbols", fake_create)

    assert main_module.run("symbols", exchange=exchange, environ={}) == 0

    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [expected_arguments]
    assert capsys.readouterr() == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


def test_run_routes_news_with_defaults_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    query = "Казахстан"
    response = {
        "result": {
            "items": [
                {
                    "title": "Новости рынка",
                    "unknown": {"nested": [True, None]},
                }
            ]
        }
    }
    use_case = FakeGetNews(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetNews:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_news", fake_create)

    exit_code = main_module.run("news", query, environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [(query, None, None, 30)]
    assert use_case.calls[0][0] is query
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Новости рынка" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_news_forwards_explicit_options_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    query = "ignored"
    symbol = "AAPL.US"
    story_id = "story-17"
    limit = 7
    use_case = FakeGetNews()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_news",
        lambda public, private: use_case,
    )

    main_module.run(
        "news",
        query,
        symbol=symbol,
        story_id=story_id,
        limit=limit,
        environ={},
    )

    assert use_case.calls == [(query, symbol, story_id, limit)]


def test_run_news_explicit_json_output_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetNews(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_news",
        lambda public, private: use_case,
    )

    main_module.run("news", "query", environ={})
    plain_output = capsys.readouterr()
    main_module.run("news", "query", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [
        ("query", None, None, 30),
        ("query", None, None, 30),
    ]
    assert plain_output == json_output
    assert plain_output == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


def test_run_market_status_uses_defaults_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "result": {
            "markets": [
                {"name": "Казахстанская фондовая биржа", "unknown": [True, None]}
            ]
        }
    }
    use_case = FakeGetMarketStatus(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetMarketStatus:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_market_status", fake_create)

    exit_code = main_module.run("market-status", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [("*", None)]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Казахстанская фондовая биржа" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_market_status_forwards_explicit_options_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    market = "KASE"
    mode = "demo"
    use_case = FakeGetMarketStatus()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_market_status",
        lambda public, private: use_case,
    )

    main_module.run(
        "market-status",
        market=market,
        mode=mode,
        environ={},
    )

    assert use_case.calls == [(market, mode)]


def test_run_market_status_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetMarketStatus(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_market_status",
        lambda public, private: use_case,
    )

    main_module.run("market-status", environ={})
    plain_output = capsys.readouterr()
    main_module.run("market-status", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [("*", None), ("*", None)]
    assert plain_output == json_output
    assert plain_output == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


def test_run_top_uses_defaults_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"result": {"items": [{"ticker": "КАЗТ", "change": 12.5}]}}
    use_case = FakeGetMostTraded(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetMostTraded:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_most_traded", fake_create)

    assert main_module.run("top", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [("stocks", "usa", True, 10)]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "КАЗТ" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_top_forwards_explicit_options_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetMostTraded()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_most_traded",
        lambda public, private: use_case,
    )

    main_module.run(
        "top",
        instrument_type="bonds",
        exchange="kase",
        gainers=False,
        limit=25,
        environ={},
    )

    assert use_case.calls == [("bonds", "kase", False, 25)]


def test_run_top_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetMostTraded(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_most_traded",
        lambda public, private: use_case,
    )

    main_module.run("top", environ={})
    plain_output = capsys.readouterr()
    main_module.run("top", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [
        ("stocks", "usa", True, 10),
        ("stocks", "usa", True, 10),
    ]
    assert plain_output == json_output


def test_run_orders_history_uses_application_defaults_and_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"result": {"orders": [{"name": "Заявка", "nested": [1, None]}]}}
    use_case = FakeGetHistorical(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetHistorical:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_historical", fake_create)

    assert main_module.run("orders-history", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [{}]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Заявка" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (
            datetime.fromisoformat("2026-01-01"),
            None,
            {"start": datetime.fromisoformat("2026-01-01")},
        ),
        (
            None,
            datetime.fromisoformat("2026-02-01"),
            {"end": datetime.fromisoformat("2026-02-01")},
        ),
        (
            datetime.fromisoformat("2026-01-01T09:30:00"),
            datetime.fromisoformat("2026-02-01T18:45:00"),
            {
                "start": datetime.fromisoformat("2026-01-01T09:30:00"),
                "end": datetime.fromisoformat("2026-02-01T18:45:00"),
            },
        ),
    ],
)
def test_run_orders_history_forwards_only_explicit_datetimes_once(
    start: datetime | None,
    end: datetime | None,
    expected: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetHistorical()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_historical",
        lambda public, private: use_case,
    )

    main_module.run("orders-history", start=start, end=end, environ={})

    assert use_case.calls == [expected]
    if start is not None:
        assert use_case.calls[0]["start"] is start
    if end is not None:
        assert use_case.calls[0]["end"] is end


def test_run_orders_history_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetHistorical(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_historical",
        lambda public, private: use_case,
    )

    main_module.run("orders-history", environ={})
    plain_output = capsys.readouterr()
    main_module.run("orders-history", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [{}, {}]
    assert plain_output == json_output


def test_run_corporate_actions_uses_default_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = [{"name": "Дивиденд", "unknown": {"nested": [True, None]}}]
    use_case = FakeGetCorporateActions(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetCorporateActions:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_corporate_actions", fake_create)

    assert main_module.run("corporate-actions", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [35]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Дивиденд" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_corporate_actions_forwards_explicit_reception_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    reception = 17
    use_case = FakeGetCorporateActions()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_corporate_actions",
        lambda public, private: use_case,
    )

    main_module.run("corporate-actions", reception=reception, environ={})

    assert use_case.calls == [reception]
    assert use_case.calls[0] is reception


def test_run_corporate_actions_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = [{"raw": {"nested": ["данные", 17, None]}}]
    use_case = FakeGetCorporateActions(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_corporate_actions",
        lambda public, private: use_case,
    )

    main_module.run("corporate-actions", environ={})
    plain_output = capsys.readouterr()
    main_module.run("corporate-actions", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [35, 35]
    assert plain_output == json_output


def test_run_price_alerts_uses_application_default_and_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"result": {"alerts": [{"name": "Цена", "nested": [1, None]}]}}
    use_case = FakeGetPriceAlerts(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetPriceAlerts:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_price_alerts", fake_create)

    assert main_module.run("price-alerts", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [{}]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Цена" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_price_alerts_forwards_explicit_symbol_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    symbol = " Aapl.US "
    use_case = FakeGetPriceAlerts()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_price_alerts",
        lambda public, private: use_case,
    )

    main_module.run("price-alerts", symbol=symbol, environ={})

    assert use_case.calls == [{"symbol": symbol}]
    assert use_case.calls[0]["symbol"] is symbol


def test_run_price_alerts_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetPriceAlerts(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_price_alerts",
        lambda public, private: use_case,
    )

    main_module.run("price-alerts", environ={})
    plain_output = capsys.readouterr()
    main_module.run("price-alerts", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [{}, {}]
    assert plain_output == json_output


def test_run_requests_history_omits_defaults_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"result": {"requests": [{"name": "Заявка", "nested": [1, None]}]}}
    use_case = FakeGetRequestsHistory(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetRequestsHistory:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_requests_history", fake_create)

    assert main_module.run("requests-history", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [{}]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Заявка" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_requests_history_forwards_only_explicit_values_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = datetime.fromisoformat("2026-01-01T09:30:00+05:00")
    end = datetime.fromisoformat("2026-02-01T18:45:00+05:00")
    use_case = FakeGetRequestsHistory()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_requests_history",
        lambda public, private: use_case,
    )

    main_module.run(
        "requests-history",
        doc_id=15,
        exec_id=23,
        start=start,
        end=end,
        limit=100,
        offset=0,
        status=3,
        environ={},
    )

    assert use_case.calls == [
        {
            "doc_id": 15,
            "exec_id": 23,
            "start": start,
            "end": end,
            "limit": 100,
            "offset": 0,
            "status": 3,
        }
    ]
    assert use_case.calls[0]["start"] is start
    assert use_case.calls[0]["end"] is end


def test_run_requests_history_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetRequestsHistory(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_requests_history",
        lambda public, private: use_case,
    )

    main_module.run("requests-history", environ={})
    plain_output = capsys.readouterr()
    main_module.run("requests-history", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [{}, {}]
    assert plain_output == json_output


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
        "label": "История",
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
    assert use_case.calls == [(symbol, {})]
    assert use_case.calls[0][0] is symbol
    assert capsys.readouterr() == (
        json.dumps(response, indent=2, ensure_ascii=False) + "\n",
        "",
    )


def test_run_routes_explicit_candles_timeframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    timeframe = int("3600")
    use_case = FakeGetHistoricalCandles()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_historical_candles",
        lambda public, private: use_case,
    )

    main_module.run("candles", "AAPL.US", timeframe=timeframe, environ={})

    assert use_case.calls == [("AAPL.US", {"timeframe": timeframe})]
    assert use_case.calls[0][1]["timeframe"] is timeframe


def test_run_routes_explicit_candles_date_range_and_timeframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = datetime.fromisoformat("2025-01-01")
    end = datetime.fromisoformat("2025-02-01")
    use_case = FakeGetHistoricalCandles()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_historical_candles",
        lambda public, private: use_case,
    )

    main_module.run(
        "candles",
        "AAPL.US",
        start=start,
        end=end,
        timeframe=3600,
        environ={},
    )

    assert use_case.calls == [
        (
            "AAPL.US",
            {"start": start, "end": end, "timeframe": 3600},
        ),
    ]


def test_run_routes_user_without_arguments_and_prints_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "name": "Иван",
        "unknown_field": {"nested": [True, None]},
    }
    use_case = FakeGetUserInfo(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetUserInfo:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_user_info", fake_create)

    exit_code = main_module.run("user", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == 1
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert "Иван" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
    assert captured.err == ""


def test_run_propagates_user_use_case_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("user request failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetUserInfo(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_user_info",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("user", environ={})

    assert exc_info.value is original
    assert use_case.calls == 1
    assert capsys.readouterr() == ("", "")


def test_run_routes_all_orders_with_false_active_and_preserves_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "title": "Все заявки",
        "orders": [{"id": 17, "status": "Исполнена"}],
        "unknown_field": {"nested": [True, None]},
    }
    use_case = FakeGetPlacedOrders(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetPlacedOrders:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_placed_orders", fake_create)

    exit_code = main_module.run("orders", active=False, environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [False]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert "Все заявки" in captured.out
    assert "Исполнена" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
    assert captured.err == ""


def test_run_routes_summary_without_arguments_and_prints_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "title": "Сводка счёта",
        "positions": [{"ticker": "AAPL.US", "quantity": "12.50"}],
        "unknown_field": {"nested": [True, None]},
    }
    use_case = FakeGetAccountSummary(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetAccountSummary:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_account_summary", fake_create)

    exit_code = main_module.run("summary", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == 1
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert "Сводка счёта" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
    assert captured.err == ""


def test_format_portfolio_renders_positions_cash_and_fractional_quantity() -> None:
    summary = {
        "result": {
            "ps": {
                "loaded": True,
                "acc": [
                    {"curr": "KZT", "s": 2.98},
                    {"curr": "USD", "s": 1.53},
                ],
                "pos": [
                    {
                        "i": "HSBK.KZ",
                        "name": "Народный банк Казахстана",
                        "q": 25,
                        "price_a": 362.625597,
                        "mkt_price": 380.5,
                        "profit_close": 389.36,
                        "market_value": 9525,
                        "curr": "KZT",
                    },
                    {
                        "i": "TINY.US",
                        "q": 0.00018,
                        "price_a": 1,
                        "mkt_price": 2,
                        "profit_close": 3,
                        "market_value": 4,
                        "curr": "USD",
                    },
                ],
            }
        }
    }

    output = main_module._format_portfolio(summary)

    assert output == (
        "Portfolio\n"
        "\n"
        "Ticker         Name                                  Qty          Avg"
        "         Last          P/L        Value   Currency\n"
        "---------------------------------------------------------------"
        "--------------------------------------------------------\n"
        "HSBK.KZ        Народный банк Казахстана               25       362.63"
        "       380.50       389.36"
        "      9525.00        KZT\n"
        "TINY.US        -                                 0.00018"
        "         1.00         2.00         3.00"
        "         4.00        USD\n"
        "\n"
        "Totals\n"
        "\n"
        "Currency              Value          P/L\n"
        "----------------------------------------\n"
        "KZT                 9525.00       389.36\n"
        "USD                    4.00         3.00\n"
        "\n"
        "Cash\n"
        "\n"
        "Currency            Balance\n"
        "---------------------------\n"
        "KZT                    2.98\n"
        "USD                    1.53"
    )
    assert "Народный банк Казахстана" in output


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ForteBank", "ForteBank"),
        ("Народный банк Казахстана", "Народный банк Казахстана"),
        (None, "-"),
        (42, "-"),
        ("", "-"),
        ("x" * 28, "x" * 28),
        ("x" * 29, "x" * 25 + "..."),
    ],
)
def test_format_portfolio_name(
    name: object,
    expected: str,
) -> None:
    assert main_module._format_portfolio_name(name) == expected
    assert len(expected) <= 28


def test_format_portfolio_truncates_name_without_mutating_response() -> None:
    long_name = "A very long instrument name beyond the column"
    position = {"i": "LONG.US", "name": long_name}
    summary = {"result": {"ps": {"pos": [position]}}}

    output = main_module._format_portfolio(summary)

    assert "A very long instrument na..." in output
    assert long_name not in output
    assert position["name"] == long_name


def test_sort_portfolio_positions_by_ticker_is_stable_and_case_insensitive() -> None:
    positions = [
        {"i": "beta"},
        {"i": "ALPHA", "marker": 1},
        {"i": "alpha", "marker": 2},
        {"i": ""},
        {"i": 42},
        {},
    ]

    result = main_module._sort_portfolio_positions(positions, "ticker")

    assert [position.get("i") for position in result] == [
        "ALPHA",
        "alpha",
        "beta",
        "",
        42,
        None,
    ]
    assert result[0]["marker"] == 1
    assert result[1]["marker"] == 2


@pytest.mark.parametrize(
    ("sort_field", "positions", "expected_tickers"),
    [
        (
            "value",
            [
                {"i": "two", "market_value": 2},
                {"i": "ten-a", "market_value": 10},
                {"i": "invalid-bool", "market_value": True},
                {"i": "ten-b", "market_value": 10},
                {"i": "invalid-string", "market_value": "100"},
            ],
            ["ten-a", "ten-b", "two", "invalid-bool", "invalid-string"],
        ),
        (
            "pnl",
            [
                {"i": "positive", "profit_close": 5},
                {"i": "loss", "profit_close": -10},
                {"i": "zero", "profit_close": 0},
                {"i": "invalid", "profit_close": None},
            ],
            ["loss", "zero", "positive", "invalid"],
        ),
        (
            "last",
            [
                {"i": "low", "mkt_price": 2},
                {"i": "high", "mkt_price": 10},
                {"i": "invalid", "mkt_price": "100"},
            ],
            ["high", "low", "invalid"],
        ),
    ],
)
def test_sort_portfolio_positions_by_numeric_field(
    sort_field: str,
    positions: list[dict[str, object]],
    expected_tickers: list[str],
) -> None:
    original_order = list(positions)

    result = main_module._sort_portfolio_positions(positions, sort_field)

    assert [position["i"] for position in result] == expected_tickers
    assert positions == original_order
    assert result is not positions


def test_filter_portfolio_positions_matches_complete_symbol_case_insensitively() -> (
    None
):
    positions = [
        {"i": "HSBK.KZ", "marker": 1},
        {"i": "hsbk.kz", "marker": 2},
        {"i": "HSBK", "marker": 3},
        {"i": ""},
        {"i": 42},
        {},
    ]
    original_order = list(positions)

    result = main_module._filter_portfolio_positions(positions, "hSbK.Kz")

    assert [position["marker"] for position in result] == [1, 2]
    assert positions == original_order
    assert result is not positions


def test_format_portfolio_filter_updates_positions_and_totals_but_not_cash() -> None:
    positions = [
        {
            "i": "HSBK.KZ",
            "market_value": 10,
            "profit_close": 1,
            "curr": "USD",
        },
        {
            "i": "OTHER.KZ",
            "market_value": 1000,
            "profit_close": 100,
            "curr": "EUR",
        },
        {
            "i": "hsbk.kz",
            "market_value": 20,
            "profit_close": 2,
            "curr": "KZT",
        },
    ]
    cash = [{"curr": "EUR", "s": 3}, {"curr": "USD", "s": 2}]
    summary = {"result": {"ps": {"pos": positions, "acc": cash}}}
    original_positions = list(positions)

    output = main_module._format_portfolio(summary, symbol="HSBK.KZ")

    assert output.count("HSBK.KZ") == 1
    assert output.count("hsbk.kz") == 1
    assert "OTHER.KZ" not in output
    totals = output.split("Totals\n\n", 1)[1].split("\n\nCash", 1)[0]
    assert totals == (
        "Currency              Value          P/L\n"
        "----------------------------------------\n"
        "USD                   10.00         1.00\n"
        "KZT                   20.00         2.00"
    )
    assert output.endswith(
        "Currency            Balance\n"
        "---------------------------\n"
        "EUR                    3.00\n"
        "USD                    2.00"
    )
    assert positions == original_positions
    assert summary["result"]["ps"]["pos"] is positions
    assert summary["result"]["ps"]["acc"] is cash


def test_format_portfolio_filters_before_sorting() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"i": "MATCH", "name": "Low", "market_value": 2},
                    {"i": "HIDDEN", "name": "Hidden", "market_value": 1000},
                    {"i": "match", "name": "High", "market_value": 10},
                ]
            }
        }
    }

    output = main_module._format_portfolio(
        summary,
        symbol="MATCH",
        sort_field="value",
    )

    assert output.index("High") < output.index("Low")
    assert "HIDDEN" not in output
    assert "Hidden" not in output


def test_format_portfolio_no_symbol_match_keeps_cash() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"i": "OTHER.KZ", "market_value": 10, "curr": "KZT"},
                    {"market_value": 20, "curr": "USD"},
                    {"i": 42, "market_value": 30, "curr": "EUR"},
                ],
                "acc": [{"curr": "KZT", "s": 2.98}],
            }
        }
    }

    output = main_module._format_portfolio(summary, symbol="HSBK.KZ")

    assert output == (
        "Portfolio\n"
        "\n"
        "No positions.\n"
        "\n"
        "Totals\n"
        "\n"
        "No totals.\n"
        "\n"
        "Cash\n"
        "\n"
        "Currency            Balance\n"
        "---------------------------\n"
        "KZT                    2.98"
    )


def test_portfolio_json_normalizes_values_and_preserves_schema_order() -> None:
    long_name = "Очень длинное название инструмента без усечения"
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {
                        "i": "HSBK.KZ",
                        "name": long_name,
                        "q": "2",
                        "price_a": "362.625",
                        "mkt_price": True,
                        "profit_close": float("nan"),
                        "market_value": "10.5",
                        "curr": "KZT",
                    },
                    {
                        "name": "",
                        "q": 0.00018,
                        "price_a": float("inf"),
                        "market_value": "invalid",
                        "curr": "",
                    },
                ],
                "acc": [
                    {"curr": "KZT", "s": "0"},
                    {"s": "1.53"},
                    "malformed",
                ],
            }
        }
    }
    original = copy.deepcopy(summary)

    result = main_module._portfolio_json(summary)

    assert list(result) == ["positions", "totals", "cash"]
    assert result == {
        "positions": [
            {
                "ticker": "HSBK.KZ",
                "name": long_name,
                "quantity": 2,
                "average_price": 362.625,
                "last_price": None,
                "profit_loss": None,
                "market_value": 10.5,
                "currency": "KZT",
            },
            {
                "ticker": None,
                "name": "",
                "quantity": 0.00018,
                "average_price": None,
                "last_price": None,
                "profit_loss": None,
                "market_value": None,
                "currency": "",
            },
        ],
        "totals": [
            {
                "currency": "KZT",
                "market_value": 10.5,
                "profit_loss": None,
            }
        ],
        "cash": [
            {"currency": "KZT", "balance": 0},
            {"currency": None, "balance": 1.53},
        ],
    }
    assert summary == original


def test_portfolio_json_filters_before_sorting_and_uses_filtered_totals() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {
                        "i": "HSBK.KZ",
                        "name": "Low",
                        "market_value": 2,
                        "curr": "USD",
                    },
                    {
                        "i": "OTHER.KZ",
                        "name": "Hidden",
                        "market_value": 1000,
                        "curr": "EUR",
                    },
                    {
                        "i": "hsbk.kz",
                        "name": "High",
                        "market_value": 10,
                        "profit_close": "-1.5",
                        "curr": "KZT",
                    },
                ]
            }
        }
    }

    result = main_module._portfolio_json(
        summary,
        symbol="HSBK.KZ",
        sort_field="value",
    )

    assert [position["name"] for position in result["positions"]] == ["High", "Low"]
    assert result["totals"] == [
        {"currency": "USD", "market_value": 2, "profit_loss": None},
        {"currency": "KZT", "market_value": 10, "profit_loss": -1.5},
    ]


def test_format_portfolio_sort_changes_only_position_rows() -> None:
    positions = [
        {
            "i": "LOW",
            "market_value": 2,
            "profit_close": 1,
            "curr": "USD",
        },
        {
            "i": "HIGH",
            "market_value": 10,
            "profit_close": 2,
            "curr": "KZT",
        },
    ]
    cash = [{"curr": "USD", "s": 1}, {"curr": "KZT", "s": 2}]
    summary = {"result": {"ps": {"pos": positions, "acc": cash}}}
    original_positions = list(positions)

    default_output = main_module._format_portfolio(summary)
    sorted_output = main_module._format_portfolio(summary, sort_field="value")

    assert default_output.index("LOW") < default_output.index("HIGH")
    assert sorted_output.index("HIGH") < sorted_output.index("LOW")
    assert (
        default_output.split("\nTotals\n", 1)[1]
        == sorted_output.split("\nTotals\n", 1)[1]
    )
    assert positions == original_positions
    assert summary["result"]["ps"]["pos"] is positions
    assert summary["result"]["ps"]["acc"] is cash


def test_format_portfolio_sort_preserves_empty_positions() -> None:
    summary = {"result": {"ps": {"pos": [], "acc": []}}}

    assert main_module._format_portfolio(summary, sort_field="ticker") == (
        "Portfolio\n\nNo positions.\n\nTotals\n\nNo totals.\n\n"
        "Cash\n\nNo cash balances."
    )


def test_format_portfolio_aggregates_multiple_positions_in_one_currency() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"curr": "KZT", "market_value": 10, "profit_close": 1.25},
                    {"curr": "KZT", "market_value": 2.5, "profit_close": 0.75},
                ]
            }
        }
    }

    output = main_module._format_portfolio(summary)

    assert (
        "Currency              Value          P/L\n"
        "----------------------------------------\n"
        "KZT                   12.50         2.00"
    ) in output


def test_format_portfolio_totals_are_independent_and_keep_currency_order() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"curr": "KZT", "market_value": 10},
                    {"curr": "USD", "market_value": 0},
                    {"curr": "KZT", "profit_close": 2.5},
                    {"curr": "EUR", "profit_close": 0},
                ]
            }
        }
    }

    output = main_module._format_portfolio(summary)
    totals = output.split("Totals\n\n", 1)[1].split("\n\nCash", 1)[0]

    assert totals == (
        "Currency              Value          P/L\n"
        "----------------------------------------\n"
        "KZT                   10.00         2.50\n"
        "USD                    0.00            -\n"
        "EUR                       -         0.00"
    )


def test_format_portfolio_ignores_invalid_totals_and_invalid_currencies() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"curr": "KZT", "market_value": True, "profit_close": "1"},
                    {
                        "curr": "USD",
                        "market_value": float("nan"),
                        "profit_close": float("inf"),
                    },
                    {"market_value": 10, "profit_close": 1},
                    {"curr": "", "market_value": 10, "profit_close": 1},
                    "not-a-position",
                ]
            }
        }
    }

    output = main_module._format_portfolio(summary)

    assert "\nTotals\n\nNo totals.\n\nCash\n" in output


def test_format_portfolio_reports_empty_positions_and_cash() -> None:
    summary = {"result": {"ps": {"pos": [], "acc": []}}}

    assert main_module._format_portfolio(summary) == (
        "Portfolio\n\nNo positions.\n\nTotals\n\nNo totals.\n\n"
        "Cash\n\nNo cash balances."
    )


@pytest.mark.parametrize(
    "summary",
    [
        None,
        {},
        {"result": None},
        {"result": {"ps": None}},
        {"result": {"ps": {"pos": "not-a-list", "acc": {"curr": "KZT"}}}},
    ],
)
def test_format_portfolio_handles_missing_or_malformed_nested_data(
    summary: object,
) -> None:
    assert main_module._format_portfolio(summary) == (
        "Portfolio\n\nNo positions.\n\nTotals\n\nNo totals.\n\n"
        "Cash\n\nNo cash balances."
    )


def test_format_portfolio_uses_placeholders_for_missing_fields_and_accepts_unicode() -> (
    None
):
    summary = {
        "result": {
            "ps": {
                "pos": [{"i": "ТЕСТ.KZ", "q": "unknown", "curr": "₸"}],
                "acc": [{"curr": "₸", "s": None}],
            }
        }
    }

    output = main_module._format_portfolio(summary)

    assert "ТЕСТ.KZ" in output
    assert "₸" in output
    assert output.splitlines()[4] == (
        "ТЕСТ.KZ        -                                       -            -"
        "            -            -            -          ₸"
    )
    assert "₸                         -" in output


def test_format_watch_renders_compact_positions_and_non_zero_cash() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [
                    {"i": "HSBK.KZ", "mkt_price": 380.5, "profit_close": 389.36},
                    {
                        "i": "ASBN.KZ",
                        "mkt_price": 9.97,
                        "profit_close": -4325.69,
                    },
                    {"i": "MISS.KZ"},
                ],
                "acc": [
                    {"curr": "KZT", "s": 2.98},
                    {"curr": "USD", "s": 0},
                    {"curr": "EUR", "s": -1.5},
                ],
            }
        }
    }

    assert main_module._format_watch(summary) == (
        "Portfolio\n"
        "\n"
        "Ticker                     Last          P/L\n"
        "--------------------------------------------\n"
        "HSBK.KZ                  380.50      +389.36\n"
        "ASBN.KZ                    9.97     -4325.69\n"
        "MISS.KZ                       -            -\n"
        "\n"
        "Cash\n"
        "\n"
        "Currency                Balance\n"
        "-------------------------------\n"
        "KZT                        2.98\n"
        "EUR                       -1.50"
    )


def test_format_watch_reports_empty_positions_and_cash() -> None:
    summary = {"result": {"ps": {"pos": [], "acc": []}}}

    assert main_module._format_watch(summary) == (
        "Portfolio\n\nNo positions.\n\nCash\n\nNo cash balances."
    )


def test_format_watch_omits_position_header_when_positions_are_empty() -> None:
    summary = {"result": {"ps": {"pos": [], "acc": [{"curr": "KZT", "s": 2.98}]}}}

    assert main_module._format_watch(summary) == (
        "Portfolio\n"
        "\n"
        "No positions.\n"
        "\n"
        "Cash\n"
        "\n"
        "Currency                Balance\n"
        "-------------------------------\n"
        "KZT                        2.98"
    )


def test_format_watch_omits_cash_header_when_cash_is_empty() -> None:
    summary = {
        "result": {
            "ps": {
                "pos": [{"i": "HSBK.KZ", "mkt_price": 380.5, "profit_close": 389.36}],
                "acc": [],
            }
        }
    }

    assert main_module._format_watch(summary) == (
        "Portfolio\n"
        "\n"
        "Ticker                     Last          P/L\n"
        "--------------------------------------------\n"
        "HSBK.KZ                  380.50      +389.36\n"
        "\n"
        "Cash\n"
        "\n"
        "No cash balances."
    )


@pytest.mark.parametrize(
    "summary",
    [
        None,
        {},
        {"result": None},
        {"result": {"ps": None}},
        {"result": {"ps": {"pos": "invalid", "acc": {"curr": "KZT"}}}},
    ],
)
def test_format_watch_handles_malformed_nested_data(summary: object) -> None:
    assert main_module._format_watch(summary) == (
        "Portfolio\n\nNo positions.\n\nCash\n\nNo cash balances."
    )


def test_format_watch_suppresses_zero_and_invalid_cash_balances() -> None:
    summary = {
        "result": {
            "ps": {
                "acc": [
                    {"curr": "KZT", "s": 0},
                    {"curr": "USD", "s": 0.0},
                    {"curr": "EUR", "s": "1.00"},
                    {"curr": "GBP", "s": True},
                ]
            }
        }
    }

    assert main_module._format_watch(summary) == (
        "Portfolio\n\nNo positions.\n\nCash\n\nNo cash balances."
    )


def test_run_routes_portfolio_through_account_summary_and_prints_text_table(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key=" PublicKey ",
        tradernet_private_key=" PrivateKey ",
    )
    response = {
        "result": {
            "ps": {
                "pos": [
                    {
                        "i": "HSBK.KZ",
                        "q": 25,
                        "price_a": 362.625597,
                        "mkt_price": 380.5,
                        "profit_close": 389.36,
                        "market_value": 9525,
                        "curr": "KZT",
                        "unknown_field": {"label": "Позиция"},
                    }
                ],
                "acc": [{"curr": "KZT", "s": 2.98}],
            }
        }
    }
    use_case = FakeGetAccountSummary(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetAccountSummary:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_account_summary", fake_create)

    exit_code = main_module.run("portfolio", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [(" PublicKey ", " PrivateKey ")]
    assert use_case.calls == 1
    assert captured.out == main_module._format_portfolio(response) + "\n"
    assert "HSBK.KZ" in captured.out
    assert "362.63" in captured.out
    assert "Позиция" not in captured.out
    assert captured.err == ""


def test_run_applies_requested_portfolio_sort(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "result": {
            "ps": {
                "pos": [
                    {"i": "LOW", "market_value": 2},
                    {"i": "HIGH", "market_value": 10},
                ]
            }
        }
    }
    use_case = FakeGetAccountSummary(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )

    exit_code = main_module.run("portfolio", sort_field="value", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert use_case.calls == 1
    assert captured.out == (
        main_module._format_portfolio(response, sort_field="value") + "\n"
    )
    assert captured.out.index("HIGH") < captured.out.index("LOW")
    assert captured.err == ""


def test_run_applies_requested_portfolio_symbol_filter(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "result": {
            "ps": {
                "pos": [
                    {"i": "HSBK.KZ"},
                    {"i": "OTHER.KZ"},
                ]
            }
        }
    }
    use_case = FakeGetAccountSummary(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )

    exit_code = main_module.run("portfolio", symbol=" HSBK.KZ ", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert use_case.calls == 1
    assert "HSBK.KZ" in captured.out
    assert "OTHER.KZ" not in captured.out
    assert captured.err == ""


def test_run_prints_normalized_portfolio_json_without_extra_text(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "result": {
            "ps": {
                "pos": [
                    {
                        "i": "HSBK.KZ",
                        "name": "Народный банк Казахстана",
                        "market_value": "10.5",
                        "curr": "KZT",
                    }
                ],
                "acc": [{"curr": "KZT", "s": "0"}],
            }
        }
    }
    use_case = FakeGetAccountSummary(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )

    exit_code = main_module.run("portfolio", json_output=True, environ={})

    captured = capsys.readouterr()
    expected = main_module._portfolio_json(response)
    assert exit_code == 0
    assert use_case.calls == 1
    assert captured.out == json.dumps(expected, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == expected
    assert "Народный банк Казахстана" in captured.out
    assert "\\u" not in captured.out
    assert not captured.out.startswith("Portfolio")
    assert captured.err == ""


def test_run_routes_watch_through_account_summary_and_prints_compact_text(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key=" PublicKey ",
        tradernet_private_key=" PrivateKey ",
    )
    response = {
        "result": {
            "ps": {
                "pos": [{"i": "HSBK.KZ", "mkt_price": 380.5, "profit_close": 389.36}],
                "acc": [{"curr": "KZT", "s": 2.98}],
            }
        }
    }
    use_case = FakeGetAccountSummary(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetAccountSummary:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_account_summary", fake_create)

    exit_code = main_module.run("watch", environ={})

    assert exit_code == 0
    assert composition_calls == [(" PublicKey ", " PrivateKey ")]
    assert use_case.calls == 1
    assert capsys.readouterr() == (main_module._format_watch(response) + "\n", "")


def test_run_watch_follow_refreshes_until_keyboard_interrupt(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    responses = [
        {"result": {"ps": {"pos": [{"i": "FIRST", "mkt_price": 1}]}}},
        {"result": {"ps": {"pos": [{"i": "SECOND", "mkt_price": 2}]}}},
    ]
    events: list[str] = []
    execute_calls = 0

    class FollowUseCase:
        def execute(self) -> dict[str, Any]:
            nonlocal execute_calls
            execute_calls += 1
            events.append(f"execute-{execute_calls}")
            if execute_calls > len(responses):
                raise KeyboardInterrupt
            return responses[execute_calls - 1]

    actual_format_watch = main_module._format_watch

    def record_format(summary: object) -> str:
        events.append("format")
        return actual_format_watch(summary)

    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: FollowUseCase(),
    )
    monkeypatch.setattr(
        main_module,
        "_clear_terminal",
        lambda: events.append("clear"),
    )
    monkeypatch.setattr(main_module, "_format_watch", record_format)
    monkeypatch.setattr(
        main_module.time,
        "sleep",
        lambda seconds: events.append(f"sleep-{seconds}"),
    )

    exit_code = main_module.run("watch", follow=True, environ={})

    assert exit_code == 0
    assert events == [
        "execute-1",
        "clear",
        "format",
        "sleep-5",
        "execute-2",
        "clear",
        "format",
        "sleep-5",
        "execute-3",
    ]
    captured = capsys.readouterr()
    assert captured == (
        actual_format_watch(responses[0])
        + "\n"
        + actual_format_watch(responses[1])
        + "\n",
        "",
    )
    assert captured.out.count("Ticker                     Last          P/L") == 2


def test_run_watch_follow_propagates_application_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("account summary failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetAccountSummary(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )
    monkeypatch.setattr(
        main_module,
        "_clear_terminal",
        lambda: pytest.fail("terminal must not be cleared"),
    )
    monkeypatch.setattr(
        main_module.time,
        "sleep",
        lambda seconds: pytest.fail("sleep must not be called"),
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("watch", follow=True, environ={})

    assert exc_info.value is original
    assert use_case.calls == 1
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize(
    ("platform_name", "expected_command"),
    [
        ("nt", "cls"),
        ("posix", "clear"),
    ],
)
def test_clear_terminal_uses_platform_command(
    platform_name: str,
    expected_command: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[str] = []
    monkeypatch.setattr(main_module.os, "name", platform_name)
    monkeypatch.setattr(
        main_module.os,
        "system",
        lambda command: commands.append(command) or 0,
    )

    main_module._clear_terminal()

    assert commands == [expected_command]


def test_run_propagates_summary_use_case_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("summary request failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetAccountSummary(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("summary", environ={})

    assert exc_info.value is original
    assert use_case.calls == 1
    assert capsys.readouterr() == ("", "")


def test_run_propagates_portfolio_use_case_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("portfolio request failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetAccountSummary(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("portfolio", environ={})

    assert exc_info.value is original
    assert use_case.calls == 1
    assert capsys.readouterr() == ("", "")


def test_run_routes_orders_without_arguments_and_prints_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "title": "Активные заявки",
        "orders": [{"id": 17, "price": "211.16"}],
        "unknown_field": {"nested": [True, None]},
    }
    use_case = FakeGetPlacedOrders(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetPlacedOrders:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_placed_orders", fake_create)

    exit_code = main_module.run("orders", environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [True]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert "Активные заявки" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
    assert captured.err == ""


def test_run_propagates_orders_use_case_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("orders request failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetPlacedOrders(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_placed_orders",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run("orders", environ={})

    assert exc_info.value is original
    assert use_case.calls == [True]
    assert capsys.readouterr() == ("", "")


def test_run_routes_trades_history_and_prints_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    trades = [{"id": 17, "price": "211.16", "title": "Сделка"}]
    response = {
        "trades": trades,
        "unknown_field": {"nested": [True, None]},
    }
    use_case = FakeGetTradesHistory(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetTradesHistory:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_trades_history", fake_create)

    exit_code = main_module.run("trades", start=start, end=end, environ={})

    captured = capsys.readouterr()
    assert exit_code == 0
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [(start, end, None, None)]
    assert use_case.calls[0][0] is start
    assert use_case.calls[0][1] is end
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert "Сделка" in captured.out
    assert "\\u" not in captured.out
    assert json.loads(captured.out) == response
    assert captured.err == ""


def test_run_trades_explicit_json_matches_existing_raw_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {
        "trades": [
            {
                "id": 17,
                "price": "211.16",
                "title": "Сделка",
                "nested": {"values": [1, None, "текст"]},
            }
        ],
        "unknown_field": {"preserved": True},
    }
    use_case = FakeGetTradesHistory(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_trades_history",
        lambda public, private: use_case,
    )

    exit_code = main_module.run(
        "trades",
        start=date(2025, 1, 1),
        end=date(2025, 2, 1),
        json_output=True,
        environ={},
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Сделка" in captured.out
    assert "текст" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_routes_trades_history_symbol_without_normalizing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    use_case = FakeGetTradesHistory()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_trades_history",
        lambda public, private: use_case,
    )

    main_module.run(
        "trades",
        start=start,
        end=end,
        symbol=symbol,
        environ={},
    )

    assert use_case.calls == [(start, end, symbol, None)]
    assert use_case.calls[0][0] is start
    assert use_case.calls[0][1] is end
    assert use_case.calls[0][2] is symbol


@pytest.mark.parametrize("limit", [0, -1, 10**100, True])
def test_run_routes_trades_history_limit_without_validation(
    limit: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    use_case = FakeGetTradesHistory()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_trades_history",
        lambda public, private: use_case,
    )

    main_module.run(
        "trades",
        start=start,
        end=end,
        limit=limit,
        environ={},
    )

    assert use_case.calls == [(start, end, None, limit)]
    assert use_case.calls[0][3] is limit


def test_run_routes_trades_history_symbol_and_limit_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    limit = 250
    use_case = FakeGetTradesHistory()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_trades_history",
        lambda public, private: use_case,
    )

    main_module.run(
        "trades",
        start=start,
        end=end,
        symbol=symbol,
        limit=limit,
        environ={},
    )

    assert use_case.calls == [(start, end, symbol, limit)]
    assert use_case.calls[0][2] is symbol
    assert use_case.calls[0][3] is limit


def test_run_propagates_trades_history_error_without_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("trades request failed")
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    use_case = FakeGetTradesHistory(error=original)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_trades_history",
        lambda public, private: use_case,
    )

    with pytest.raises(RuntimeError) as exc_info:
        main_module.run(
            "trades",
            start=date(2025, 1, 1),
            end=date(2025, 2, 1),
            environ={},
        )

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


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


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (
            ["news", "market"],
            {"symbol": None, "story_id": None, "limit": 30},
        ),
        (
            [
                "news",
                "market",
                "--symbol",
                "AAPL.US",
                "--story-id",
                "story-17",
                "--limit",
                "7",
                "--json",
            ],
            {
                "symbol": "AAPL.US",
                "story_id": "story-17",
                "limit": 7,
                "json_output": True,
            },
        ),
        (
            [
                "news",
                "market",
                "--json",
                "--limit",
                "7",
                "--story-id",
                "story-17",
                "--symbol",
                "AAPL.US",
            ],
            {
                "symbol": "AAPL.US",
                "story_id": "story-17",
                "limit": 7,
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_news_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def fake_run(command: str, query: str, **options: object) -> int:
        calls.append((command, query, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("news", "market", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["symbols"], {}),
        (["symbols", "--exchange", "KASE"], {"exchange": "KASE"}),
        (
            ["symbols", "--json", "--exchange", "KASE"],
            {"exchange": "KASE", "json_output": True},
        ),
    ],
)
def test_main_routes_symbols_options(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("symbols", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["market-status"], {}),
        (
            ["market-status", "--market", "KASE"],
            {"market": "KASE", "mode": None},
        ),
        (
            ["market-status", "--mode", "demo"],
            {"market": "*", "mode": "demo"},
        ),
        (
            [
                "market-status",
                "--json",
                "--mode",
                "demo",
                "--market",
                "KASE",
            ],
            {
                "market": "KASE",
                "mode": "demo",
                "json_output": True,
            },
        ),
        (
            [
                "market-status",
                "--market",
                "KASE",
                "--json",
                "--mode",
                "demo",
            ],
            {
                "market": "KASE",
                "mode": "demo",
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_market_status_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("market-status", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["top"], {}),
        (
            ["top", "--type", "bonds"],
            {
                "instrument_type": "bonds",
                "exchange": "usa",
                "gainers": True,
                "limit": 10,
            },
        ),
        (
            ["top", "--exchange", "kase"],
            {
                "instrument_type": "stocks",
                "exchange": "kase",
                "gainers": True,
                "limit": 10,
            },
        ),
        (
            ["top", "--limit", "25"],
            {
                "instrument_type": "stocks",
                "exchange": "usa",
                "gainers": True,
                "limit": 25,
            },
        ),
        (
            ["top", "--losers"],
            {
                "instrument_type": "stocks",
                "exchange": "usa",
                "gainers": False,
                "limit": 10,
            },
        ),
        (
            [
                "top",
                "--json",
                "--limit",
                "7",
                "--exchange",
                "kase",
                "--losers",
                "--type",
                "bonds",
            ],
            {
                "instrument_type": "bonds",
                "exchange": "kase",
                "gainers": False,
                "limit": 7,
                "json_output": True,
            },
        ),
        (
            [
                "top",
                "--type",
                "bonds",
                "--losers",
                "--exchange",
                "kase",
                "--json",
                "--limit",
                "7",
            ],
            {
                "instrument_type": "bonds",
                "exchange": "kase",
                "gainers": False,
                "limit": 7,
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_top_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("top", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["orders-history"], {}),
        (
            ["orders-history", "--start", "2026-01-01"],
            {"start": datetime.fromisoformat("2026-01-01")},
        ),
        (
            ["orders-history", "--end", "2026-02-01T18:45:00"],
            {"end": datetime.fromisoformat("2026-02-01T18:45:00")},
        ),
        (
            [
                "orders-history",
                "--start",
                "2026-01-01T09:30:00+05:00",
                "--end",
                "2026-02-01T18:45:00+05:00",
            ],
            {
                "start": datetime.fromisoformat("2026-01-01T09:30:00+05:00"),
                "end": datetime.fromisoformat("2026-02-01T18:45:00+05:00"),
            },
        ),
        (
            [
                "orders-history",
                "--json",
                "--end",
                "2026-02-01",
                "--start",
                "2026-01-01T09:30:00",
            ],
            {
                "start": datetime.fromisoformat("2026-01-01T09:30:00"),
                "end": datetime.fromisoformat("2026-02-01"),
                "json_output": True,
            },
        ),
        (
            [
                "orders-history",
                "--start",
                "2026-01-01T09:30:00",
                "--json",
                "--end",
                "2026-02-01",
            ],
            {
                "start": datetime.fromisoformat("2026-01-01T09:30:00"),
                "end": datetime.fromisoformat("2026-02-01"),
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_orders_history_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("orders-history", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["corporate-actions"], {}),
        (
            ["corporate-actions", "--reception", "17"],
            {"reception": 17},
        ),
        (
            ["corporate-actions", "--json", "--reception", "17"],
            {"reception": 17, "json_output": True},
        ),
        (
            ["corporate-actions", "--reception", "17", "--json"],
            {"reception": 17, "json_output": True},
        ),
    ],
)
def test_main_routes_corporate_actions_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("corporate-actions", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["price-alerts"], {}),
        (
            ["price-alerts", "--symbol", " Aapl.US "],
            {"symbol": " Aapl.US "},
        ),
        (
            ["price-alerts", "--json", "--symbol", "AAPL.US"],
            {"symbol": "AAPL.US", "json_output": True},
        ),
        (
            ["price-alerts", "--symbol", "AAPL.US", "--json"],
            {"symbol": "AAPL.US", "json_output": True},
        ),
    ],
)
def test_main_routes_price_alerts_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("price-alerts", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["requests-history"], {}),
        (["requests-history", "--doc-id", "15"], {"doc_id": 15}),
        (["requests-history", "--exec-id", "23"], {"exec_id": 23}),
        (
            ["requests-history", "--start", "2026-01-01"],
            {"start": datetime.fromisoformat("2026-01-01")},
        ),
        (
            ["requests-history", "--end", "2026-02-01T18:45:00+05:00"],
            {"end": datetime.fromisoformat("2026-02-01T18:45:00+05:00")},
        ),
        (["requests-history", "--limit", "100"], {"limit": 100}),
        (["requests-history", "--offset", "0"], {"offset": 0}),
        (["requests-history", "--status", "-1"], {"status": -1}),
        (
            ["requests-history", "--json"],
            {"json_output": True},
        ),
        (
            [
                "requests-history",
                "--status",
                "3",
                "--limit",
                "100",
                "--doc-id",
                "1",
                "--end",
                "2026-02-01",
                "--json",
                "--start",
                "2026-01-01T09:30:00+05:00",
                "--offset",
                "10",
                "--exec-id",
                "2",
            ],
            {
                "doc_id": 1,
                "exec_id": 2,
                "start": datetime.fromisoformat("2026-01-01T09:30:00+05:00"),
                "end": datetime.fromisoformat("2026-02-01"),
                "limit": 100,
                "offset": 10,
                "status": 3,
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_requests_history_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("requests-history", expected_options)]


def test_main_routes_user_without_operation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run(command: str) -> int:
        calls.append(command)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["user"]) == 17
    assert calls == ["user"]


def test_main_routes_summary_without_operation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run(command: str) -> int:
        calls.append(command)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["summary"]) == 17
    assert calls == ["summary"]


def test_main_routes_portfolio_without_operation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run(command: str) -> int:
        calls.append(command)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["portfolio"]) == 17
    assert calls == ["portfolio"]


@pytest.mark.parametrize("sort_field", ["ticker", "value", "pnl", "last"])
def test_main_routes_portfolio_sort(
    sort_field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_run(command: str, *, sort_field: str) -> int:
        calls.append((command, sort_field))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["portfolio", "--sort", sort_field]) == 17
    assert calls == [("portfolio", sort_field)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["portfolio", "--symbol", " HSBK.KZ "], {"symbol": "HSBK.KZ"}),
        (
            ["portfolio", "--symbol", "HSBK.KZ", "--sort", "pnl"],
            {"symbol": "HSBK.KZ", "sort_field": "pnl"},
        ),
        (
            ["portfolio", "--sort", "pnl", "--symbol", "HSBK.KZ"],
            {"symbol": "HSBK.KZ", "sort_field": "pnl"},
        ),
    ],
)
def test_main_routes_portfolio_symbol_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("portfolio", expected_options)]


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["portfolio", "--json"], {"json_output": True}),
        (
            ["portfolio", "--symbol", " HSBK.KZ ", "--json"],
            {"symbol": "HSBK.KZ", "json_output": True},
        ),
        (
            ["portfolio", "--json", "--symbol", "HSBK.KZ"],
            {"symbol": "HSBK.KZ", "json_output": True},
        ),
        (
            ["portfolio", "--sort", "pnl", "--json"],
            {"sort_field": "pnl", "json_output": True},
        ),
        (
            ["portfolio", "--json", "--sort", "pnl"],
            {"sort_field": "pnl", "json_output": True},
        ),
        (
            [
                "portfolio",
                "--symbol",
                "HSBK.KZ",
                "--sort",
                "pnl",
                "--json",
            ],
            {"symbol": "HSBK.KZ", "sort_field": "pnl", "json_output": True},
        ),
        (
            [
                "portfolio",
                "--json",
                "--sort",
                "pnl",
                "--symbol",
                "HSBK.KZ",
            ],
            {"symbol": "HSBK.KZ", "sort_field": "pnl", "json_output": True},
        ),
    ],
)
def test_main_routes_portfolio_json_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("portfolio", expected_options)]


def test_main_routes_watch_without_operation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run(command: str) -> int:
        calls.append(command)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["watch"]) == 17
    assert calls == ["watch"]


def test_main_routes_watch_follow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_run(command: str, *, follow: bool) -> int:
        calls.append((command, follow))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["watch", "--follow"]) == 17
    assert calls == [("watch", True)]


def test_main_routes_orders_without_operation_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_run(command: str) -> int:
        calls.append(command)
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["orders"]) == 17
    assert calls == ["orders"]


def test_main_routes_orders_all_with_false_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, bool]] = []

    def fake_run(command: str, *, active: bool) -> int:
        calls.append((command, active))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["orders", "--all"]) == 17
    assert calls == [("orders", False)]


@pytest.mark.parametrize(
    ("arguments", "expected_symbol", "expected_limit"),
    [
        (
            ["trades", "--from", "2025-01-01", "--to", "2025-02-01"],
            None,
            None,
        ),
        (
            ["trades", "--to", "2025-02-01", "--from", "2025-01-01"],
            None,
            None,
        ),
        (
            [
                "trades",
                "--from",
                "2025-01-01",
                "--symbol",
                "AAPL.US",
                "--to",
                "2025-02-01",
            ],
            "AAPL.US",
            None,
        ),
        (
            [
                "trades",
                "--limit",
                "100",
                "--to",
                "2025-02-01",
                "--from",
                "2025-01-01",
            ],
            None,
            100,
        ),
        (
            [
                "trades",
                "--symbol",
                "AAPL.US",
                "--limit",
                "100",
                "--from",
                "2025-01-01",
                "--to",
                "2025-02-01",
            ],
            "AAPL.US",
            100,
        ),
        (
            [
                "trades",
                "--to",
                "2025-02-01",
                "--limit",
                "-1",
                "--symbol",
                "AAPL.US",
                "--from",
                "2025-01-01",
            ],
            "AAPL.US",
            -1,
        ),
        (
            [
                "trades",
                "--from",
                "2025-01-01",
                "--to",
                "2025-02-01",
                "--limit",
                "0",
            ],
            None,
            0,
        ),
        (
            [
                "trades",
                "--from",
                "2025-01-01",
                "--to",
                "2025-02-01",
                "--limit",
                str(10**100),
            ],
            None,
            10**100,
        ),
    ],
)
def test_main_routes_trades_date_range_in_any_flag_order(
    arguments: list[str],
    expected_symbol: str | None,
    expected_limit: int | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, date, date, str | None, int | None]] = []

    def fake_run(
        command: str,
        *,
        start: date,
        end: date,
        symbol: str | None,
        limit: int | None,
    ) -> int:
        calls.append((command, start, end, symbol, limit))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [
        (
            "trades",
            date(2025, 1, 1),
            date(2025, 2, 1),
            expected_symbol,
            expected_limit,
        )
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--json",
        ],
        [
            "trades",
            "--json",
            "--symbol",
            "AAPL.US",
            "--limit",
            "100",
            "--to",
            "2025-02-01",
            "--from",
            "2025-01-01",
        ],
        [
            "trades",
            "--limit",
            "100",
            "--from",
            "2025-01-01",
            "--json",
            "--to",
            "2025-02-01",
            "--symbol",
            "AAPL.US",
        ],
    ],
)
def test_main_routes_trades_json_with_options_in_any_order(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **kwargs: object) -> int:
        calls.append((command, kwargs))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [
        (
            "trades",
            {
                "start": date(2025, 1, 1),
                "end": date(2025, 2, 1),
                "symbol": "AAPL.US" if "--symbol" in arguments else None,
                "limit": 100 if "--limit" in arguments else None,
                "json_output": True,
            },
        )
    ]


@pytest.mark.parametrize("value", [3600, 0, -60])
def test_main_passes_candles_timeframe(
    value: int,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, int]] = []

    def fake_run(command: str, symbol: str, *, timeframe: int) -> int:
        calls.append((command, symbol, timeframe))
        return 0

    monkeypatch.setattr(main_module, "run", fake_run)

    assert (
        main_module.main(
            ["candles", "AAPL.US", "--timeframe", str(value)],
        )
        == 0
    )
    assert calls == [("candles", "AAPL.US", value)]


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        (
            ["--from", "2025-01-01"],
            {"start": datetime.fromisoformat("2025-01-01")},
        ),
        (
            ["--to", "2025-02-01"],
            {"end": datetime.fromisoformat("2025-02-01")},
        ),
        (
            ["--to", "2025-02-01", "--from", "2025-01-01"],
            {
                "start": datetime.fromisoformat("2025-01-01"),
                "end": datetime.fromisoformat("2025-02-01"),
            },
        ),
        (
            [
                "--timeframe",
                "3600",
                "--from",
                "2025-01-01",
                "--to",
                "2025-02-01",
            ],
            {
                "start": datetime.fromisoformat("2025-01-01"),
                "end": datetime.fromisoformat("2025-02-01"),
                "timeframe": 3600,
            },
        ),
    ],
)
def test_main_passes_candles_date_options_in_any_order(
    options: list[str],
    expected: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, dict[str, object]]] = []

    def fake_run(command: str, symbol: str, **kwargs: object) -> int:
        calls.append((command, symbol, kwargs))
        return 0

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(["candles", "AAPL.US", *options]) == 0
    assert calls == [("candles", "AAPL.US", expected)]


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


def test_main_formats_portfolio_configuration_error(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = "Missing required environment variable: TRADERNET_PUBLIC_KEY"

    def fail_run(command: str) -> None:
        assert command == "portfolio"
        raise ConfigurationError(message)

    monkeypatch.setattr(main_module, "run", fail_run)

    assert main_module.main(["portfolio"]) == 1
    assert capsys.readouterr() == ("", message + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["portfolio", "extra"],
        ["portfolio", "--anything"],
        ["portfolio", "--sort"],
        ["portfolio", "--sort", "unknown"],
        ["portfolio", "--sort", "ticker", "extra"],
        ["portfolio", "--sort", "ticker", "--sort", "value"],
        ["portfolio", "--symbol"],
        ["portfolio", "--symbol", ""],
        ["portfolio", "--symbol", "   "],
        ["portfolio", "--symbol", "HSBK.KZ", "--symbol", "AAPL.US"],
        ["portfolio", "--symbol", "HSBK.KZ", "--unknown", "value"],
        ["portfolio", "--symbol", "HSBK.KZ", "extra"],
        ["portfolio", "--json", "--json"],
        ["portfolio", "--json", "extra"],
        ["portfolio", "--json", "--symbol"],
    ],
)
def test_main_rejects_invalid_portfolio_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_account_summary",
        lambda *args, **kwargs: orchestration_calls.append("factory"),
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["news"],
        ["news", "--json"],
        ["news", "--unknown"],
        ["news", "query", "extra"],
        ["news", "query", "--unknown"],
        ["news", "query", "--symbol"],
        ["news", "query", "--story-id"],
        ["news", "query", "--limit"],
        ["news", "query", "--symbol", "--json"],
        ["news", "query", "--symbol", "--unknown"],
        ["news", "query", "--story-id", "--limit"],
        ["news", "query", "--limit", "invalid"],
        ["news", "query", "--limit", "1.5"],
        ["news", "query", "--limit", "0"],
        ["news", "query", "--limit", "-1"],
        ["news", "query", "--json", "--json"],
        ["news", "query", "--symbol", "AAPL.US", "--symbol", "MSFT.US"],
        ["news", "query", "--story-id", "one", "--story-id", "two"],
        ["news", "query", "--limit", "7", "--limit", "8"],
    ],
)
def test_main_rejects_invalid_news_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_news",
        lambda *args, **kwargs: orchestration_calls.append("factory"),
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["market-status", "extra"],
        ["market-status", "--unknown"],
        ["market-status", "--market"],
        ["market-status", "--mode"],
        ["market-status", "--market", "--json"],
        ["market-status", "--mode", "--unknown"],
        ["market-status", "--json", "--json"],
        ["market-status", "--market", "KASE", "--market", "USA"],
        ["market-status", "--mode", "demo", "--mode", "real"],
        ["market-status", "--market", "KASE", "extra"],
    ],
)
def test_main_rejects_invalid_market_status_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_market_status",
        lambda *args, **kwargs: orchestration_calls.append("factory"),
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["symbols", "extra"],
        ["symbols", "--unknown"],
        ["symbols", "--exchange"],
        ["symbols", "--exchange", "--json"],
        ["symbols", "--json", "--json"],
        ["symbols", "--exchange", "KASE", "--exchange", "USA"],
    ],
)
def test_main_rejects_invalid_symbols_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetSymbols()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_symbols",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["top", "extra"],
        ["top", "--unknown"],
        ["top", "--type"],
        ["top", "--exchange"],
        ["top", "--limit"],
        ["top", "--type", "--json"],
        ["top", "--exchange", "--losers"],
        ["top", "--limit", "invalid"],
        ["top", "--limit", "1.5"],
        ["top", "--limit", "0"],
        ["top", "--limit", "-1"],
        ["top", "--json", "--json"],
        ["top", "--losers", "--losers"],
        ["top", "--type", "stocks", "--type", "bonds"],
        ["top", "--exchange", "usa", "--exchange", "kase"],
        ["top", "--limit", "10", "--limit", "20"],
        ["top", "--type", "stocks", "extra"],
    ],
)
def test_main_rejects_invalid_top_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_most_traded",
        lambda *args, **kwargs: orchestration_calls.append("factory"),
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["orders-history", "extra"],
        ["orders-history", "--unknown"],
        ["orders-history", "--start"],
        ["orders-history", "--end"],
        ["orders-history", "--start", "--json"],
        ["orders-history", "--end", "--unknown"],
        ["orders-history", "--start", "not-a-datetime"],
        ["orders-history", "--end", "2026-13-01"],
        ["orders-history", "--json", "--json"],
        [
            "orders-history",
            "--start",
            "2026-01-01",
            "--start",
            "2026-02-01",
        ],
        ["orders-history", "--end", "2026-01-01", "--end", "2026-02-01"],
        ["orders-history", "--start", "2026-01-01", "extra"],
    ],
)
def test_main_rejects_invalid_orders_history_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetHistorical()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_historical",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["corporate-actions", "extra"],
        ["corporate-actions", "--unknown"],
        ["corporate-actions", "--reception"],
        ["corporate-actions", "--reception", "--json"],
        ["corporate-actions", "--reception", "invalid"],
        ["corporate-actions", "--reception", "1.5"],
        ["corporate-actions", "--reception", "0"],
        ["corporate-actions", "--reception", "-1"],
        ["corporate-actions", "--json", "--json"],
        [
            "corporate-actions",
            "--reception",
            "17",
            "--reception",
            "35",
        ],
        ["corporate-actions", "--reception", "17", "extra"],
    ],
)
def test_main_rejects_invalid_corporate_actions_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetCorporateActions()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_corporate_actions",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["price-alerts", "extra"],
        ["price-alerts", "--unknown"],
        ["price-alerts", "--symbol"],
        ["price-alerts", "--symbol", "--json"],
        ["price-alerts", "--json", "--json"],
        [
            "price-alerts",
            "--symbol",
            "AAPL.US",
            "--symbol",
            "MSFT.US",
        ],
        ["price-alerts", "--symbol", "AAPL.US", "extra"],
    ],
)
def test_main_rejects_invalid_price_alerts_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetPriceAlerts()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_price_alerts",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        ["requests-history", "extra"],
        ["requests-history", "--unknown"],
        ["requests-history", "--doc-id"],
        ["requests-history", "--exec-id"],
        ["requests-history", "--start"],
        ["requests-history", "--end"],
        ["requests-history", "--limit"],
        ["requests-history", "--offset"],
        ["requests-history", "--status"],
        ["requests-history", "--doc-id", "--json"],
        ["requests-history", "--doc-id", "invalid"],
        ["requests-history", "--exec-id", "1.5"],
        ["requests-history", "--start", "not-a-datetime"],
        ["requests-history", "--end", "2026-13-01"],
        ["requests-history", "--limit", "invalid"],
        ["requests-history", "--limit", "0"],
        ["requests-history", "--limit", "-1"],
        ["requests-history", "--offset", "invalid"],
        ["requests-history", "--offset", "-1"],
        ["requests-history", "--status", "invalid"],
        ["requests-history", "--json", "--json"],
        ["requests-history", "--doc-id", "1", "--doc-id", "2"],
        ["requests-history", "--exec-id", "1", "--exec-id", "2"],
        ["requests-history", "--start", "2026-01-01", "--start", "2026-02-01"],
        ["requests-history", "--end", "2026-01-01", "--end", "2026-02-01"],
        ["requests-history", "--limit", "1", "--limit", "2"],
        ["requests-history", "--offset", "1", "--offset", "2"],
        ["requests-history", "--status", "1", "--status", "2"],
        ["requests-history", "--doc-id", "1", "extra"],
    ],
)
def test_main_rejects_invalid_requests_history_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetRequestsHistory()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_requests_history",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["info"],
        ["quotes"],
        ["search"],
        ["candles"],
        ["user", "extra"],
        ["user", "--anything"],
        ["user", "user"],
        ["summary", "extra"],
        ["summary", "--anything"],
        ["summary", "summary"],
        ["portfolio", "extra"],
        ["portfolio", "--anything"],
        ["watch", "extra"],
        ["watch", "--anything"],
        ["watch", "--follow", "extra"],
        ["watch", "--follow", "--follow"],
        ["orders", "extra"],
        ["orders", "--anything"],
        ["orders", "orders"],
        ["orders", "--all", "extra"],
        ["orders", "--all", "--all"],
        ["trades"],
        ["trades", "--from", "2025-01-01"],
        ["trades", "--to", "2025-02-01"],
        ["trades", "--symbol", "AAPL.US"],
        ["trades", "--limit", "100"],
        ["trades", "--from"],
        ["trades", "--to"],
        ["trades", "--symbol"],
        ["trades", "--limit"],
        ["trades", "--from", "invalid", "--to", "2025-02-01"],
        ["trades", "--from", "2025-01-01", "--to", "invalid"],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--limit",
            "invalid",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--limit",
            "1.5",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--limit",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--from",
            "2025-01-02",
            "--to",
            "2025-02-01",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--to",
            "2025-03-01",
        ],
        ["trades", "--unknown", "value"],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--symbol",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--symbol",
            "AAPL.US",
            "--symbol",
            "MSFT.US",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--limit",
            "10",
            "--limit",
            "20",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--json",
            "--json",
        ],
        [
            "trades",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
            "--json",
            "extra",
        ],
        [
            "trades",
            "extra",
            "--from",
            "2025-01-01",
            "--to",
            "2025-02-01",
        ],
        ["info", "AAPL.US", "extra"],
        ["search", "Apple", "extra"],
        ["candles", "AAPL.US", "extra"],
        ["candles", "AAPL.US", "--timeframe"],
        ["candles", "AAPL.US", "--timeframe", "hour"],
        ["candles", "AAPL.US", "--from"],
        ["candles", "AAPL.US", "--to"],
        ["candles", "AAPL.US", "--from", "2025/01/01"],
        ["candles", "AAPL.US", "--to", "2025-02-30"],
        ["candles", "AAPL.US", "--unknown", "3600"],
        ["candles", "AAPL.US", "--timeframe", "3600", "extra"],
        [
            "candles",
            "AAPL.US",
            "--from",
            "2025-01-01",
            "--from",
            "2025-02-01",
        ],
        ["info", "AAPL.US", "--timeframe", "3600"],
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
        "  kase-pilot symbols [--exchange EXCHANGE] [--json]\n"
        "  kase-pilot news QUERY [--symbol SYMBOL] [--story-id STORY_ID] "
        "[--limit LIMIT] [--json]\n"
        "  kase-pilot market-status [--market MARKET] [--mode MODE] [--json]\n"
        "  kase-pilot top [--type TYPE] [--exchange EXCHANGE] [--limit LIMIT] "
        "[--losers] [--json]\n"
        "  kase-pilot orders-history [--start DATETIME] [--end DATETIME] [--json]\n"
        "  kase-pilot corporate-actions [--reception DAYS] [--json]\n"
        "  kase-pilot price-alerts [--symbol SYMBOL] [--json]\n"
        "  kase-pilot requests-history [--doc-id ID] [--exec-id ID] "
        "[--start DATE] [--end DATE] [--limit LIMIT] [--offset OFFSET] "
        "[--status STATUS] [--json]\n"
        "  kase-pilot broker-report [--start DATE] [--end DATE] [--period TIME] "
        "[--json]\n"
        "  kase-pilot user\n"
        "  kase-pilot summary\n"
        "  kase-pilot portfolio [--symbol SYMBOL] "
        "[--sort ticker|value|pnl|last] [--json]\n"
        "  kase-pilot watch [--follow]\n"
        "  kase-pilot orders [--all]\n"
        "  kase-pilot trades --from YYYY-MM-DD --to YYYY-MM-DD "
        "[--symbol SYMBOL] [--limit NUMBER] [--json]\n"
        "  kase-pilot candles SYMBOL [--from YYYY-MM-DD] [--to YYYY-MM-DD] "
        "[--timeframe SECONDS]\n"
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


def test_run_broker_report_omits_defaults_and_prints_raw_pretty_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"trades": [{"name": "Сделка", "nested": [1, None]}]}
    use_case = FakeGetBrokerReport(response)
    composition_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)

    def fake_create(public: str, private: str) -> FakeGetBrokerReport:
        composition_calls.append((public, private))
        return use_case

    monkeypatch.setattr(main_module, "create_get_broker_report", fake_create)

    assert main_module.run("broker-report", environ={}) == 0

    captured = capsys.readouterr()
    assert composition_calls == [("PublicKey", "PrivateKey")]
    assert use_case.calls == [{}]
    assert captured.out == json.dumps(response, indent=2, ensure_ascii=False) + "\n"
    assert json.loads(captured.out) == response
    assert "Сделка" in captured.out
    assert "\\u" not in captured.out
    assert captured.err == ""


def test_run_broker_report_forwards_only_explicit_values_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    period = time.fromisoformat("18:30:15.123456+05:00")
    use_case = FakeGetBrokerReport()
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_broker_report",
        lambda public, private: use_case,
    )

    assert (
        main_module.run(
            "broker-report",
            start=start,
            end=end,
            period=period,
            environ={},
        )
        == 0
    )

    assert use_case.calls == [{"start": start, "end": end, "period": period}]
    assert use_case.calls[0]["start"] is start
    assert use_case.calls[0]["end"] is end
    assert use_case.calls[0]["period"] is period


def test_run_broker_report_explicit_json_matches_plain_output(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        tradernet_public_key="PublicKey",
        tradernet_private_key="PrivateKey",
    )
    response = {"raw": {"nested": ["данные", 17, None]}}
    use_case = FakeGetBrokerReport(response)
    monkeypatch.setattr(main_module, "load_settings", lambda *args, **kwargs: settings)
    monkeypatch.setattr(
        main_module,
        "create_get_broker_report",
        lambda public, private: use_case,
    )

    main_module.run("broker-report", environ={})
    plain_output = capsys.readouterr()
    main_module.run("broker-report", json_output=True, environ={})
    json_output = capsys.readouterr()

    assert use_case.calls == [{}, {}]
    assert plain_output == json_output


@pytest.mark.parametrize(
    ("arguments", "expected_options"),
    [
        (["broker-report"], {}),
        (
            ["broker-report", "--start", "2026-01-01"],
            {"start": date(2026, 1, 1)},
        ),
        (
            ["broker-report", "--end", "2026-01-31"],
            {"end": date(2026, 1, 31)},
        ),
        (
            ["broker-report", "--period", "18:30:15"],
            {"period": time(18, 30, 15)},
        ),
        (
            ["broker-report", "--period", "18:30:15.123456"],
            {"period": time(18, 30, 15, 123456)},
        ),
        (
            ["broker-report", "--period", "18:30:15+05:00"],
            {"period": time.fromisoformat("18:30:15+05:00")},
        ),
        (
            [
                "broker-report",
                "--json",
                "--period",
                "18:30:15",
                "--end",
                "2026-01-31",
                "--start",
                "2026-01-01",
            ],
            {
                "start": date(2026, 1, 1),
                "end": date(2026, 1, 31),
                "period": time(18, 30, 15),
                "json_output": True,
            },
        ),
    ],
)
def test_main_routes_broker_report_options_in_any_order(
    arguments: list[str],
    expected_options: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_run(command: str, **options: object) -> int:
        calls.append((command, options))
        return 17

    monkeypatch.setattr(main_module, "run", fake_run)

    assert main_module.main(arguments) == 17
    assert calls == [("broker-report", expected_options)]


@pytest.mark.parametrize(
    "arguments",
    [
        ["broker-report", "--start"],
        ["broker-report", "--end"],
        ["broker-report", "--period"],
        ["broker-report", "--start", "--json"],
        ["broker-report", "--start", "not-a-date"],
        ["broker-report", "--start", "2026-01-01T09:30:00"],
        ["broker-report", "--end", "2026-13-01"],
        ["broker-report", "--period", "not-a-time"],
        ["broker-report", "--period", "25:00:00"],
        ["broker-report", "--json", "--json"],
        ["broker-report", "--start", "2026-01-01", "--start", "2026-02-01"],
        ["broker-report", "--end", "2026-01-01", "--end", "2026-02-01"],
        ["broker-report", "--period", "12:00", "--period", "13:00"],
        ["broker-report", "--unknown"],
        ["broker-report", "extra"],
    ],
)
def test_main_rejects_invalid_broker_report_before_orchestration(
    arguments: list[str],
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orchestration_calls: list[str] = []
    use_case = FakeGetBrokerReport()
    monkeypatch.setattr(
        main_module,
        "run",
        lambda *args, **kwargs: orchestration_calls.append("run"),
    )
    monkeypatch.setattr(
        main_module,
        "load_settings",
        lambda *args, **kwargs: orchestration_calls.append("settings"),
    )
    monkeypatch.setattr(
        main_module,
        "create_get_broker_report",
        lambda *args, **kwargs: orchestration_calls.append("factory") or use_case,
    )

    assert main_module.main(arguments) == 2
    assert orchestration_calls == []
    assert use_case.calls == []
    assert capsys.readouterr() == ("", main_module._USAGE + "\n")
