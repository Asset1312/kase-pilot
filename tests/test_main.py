"""Tests for the KASE Pilot application entry point."""

import json
import sys
import tomllib
from datetime import date, datetime
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
        "HSBK.KZ                  380.50      +389.36\n"
        "ASBN.KZ                    9.97     -4325.69\n"
        "MISS.KZ                       -            -\n"
        "\n"
        "Cash\n"
        "\n"
        "KZT                        2.98\n"
        "EUR                       -1.50"
    )


def test_format_watch_reports_empty_positions_and_cash() -> None:
    summary = {"result": {"ps": {"pos": [], "acc": []}}}

    assert main_module._format_watch(summary) == (
        "Portfolio\n\nNo positions.\n\nCash\n\nNo cash balances."
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
        "  kase-pilot user\n"
        "  kase-pilot summary\n"
        "  kase-pilot portfolio\n"
        "  kase-pilot watch\n"
        "  kase-pilot orders [--all]\n"
        "  kase-pilot trades --from YYYY-MM-DD --to YYYY-MM-DD "
        "[--symbol SYMBOL] [--limit NUMBER]\n"
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
