"""Tests for the market-data broker service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker.market import MarketService


class FakeSecurityInfoDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []

    def get_security_info(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, Any]:
        self.calls.append((ticker, sup))
        return self.response


class FakeQuotesDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_quotes(self, symbols: object) -> dict[str, Any]:
        self.calls.append(symbols)
        return self.response


class FakeFindSymbolDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def find_symbol(self, query: object) -> dict[str, Any]:
        self.calls.append(query)
        return self.response


class FakeNewsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object, object]] = []

    def get_news(
        self,
        query: object,
        *,
        symbol: object = None,
        story_id: object = None,
        limit: object = 30,
    ) -> dict[str, Any]:
        self.calls.append((query, symbol, story_id, limit))
        return self.response


class FakeCandlesDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object, object]] = []

    def get_candles(
        self,
        symbol: object,
        start: object,
        end: object,
        timeframe: object,
    ) -> dict[str, Any]:
        self.calls.append((symbol, start, end, timeframe))
        return self.response


def test_get_security_info_passes_ticker_and_default_sup_once() -> None:
    dependency = FakeSecurityInfoDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_security_info(" aapl.us ")

    assert dependency.calls == [(" aapl.us ", True)]


def test_get_security_info_passes_false_sup() -> None:
    dependency = FakeSecurityInfoDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_security_info("AAPL.US", sup=False)

    assert dependency.calls == [("AAPL.US", False)]


def test_get_security_info_returns_response_unchanged() -> None:
    response = {
        "nt_ticker": "AAPL.US",
        "min_step": "0.01",
        "lot": "1",
        "unknown_field": {"nested": True},
    }
    dependency = FakeSecurityInfoDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_security_info("AAPL.US")

    assert result is response
    assert result["min_step"] == "0.01"
    assert result["lot"] == "1"
    assert "unknown_field" in result
    assert "mrkt" not in result


def test_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_security_info(
            self,
            ticker: str,
            *,
            sup: bool = True,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_security_info("AAPL.US")

    assert exc_info.value is original


def test_get_quotes_delegates_without_transforming_symbols_or_response() -> None:
    symbols = ["AAPL.US", "MSFT.US", "AAPL.US"]
    response = {
        "quotes": {
            "AAPL.US": {
                "last": "211.16",
                "unknown_field": {"nested": [True, None]},
            }
        }
    }
    dependency = FakeQuotesDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_quotes(symbols)

    assert dependency.calls == [symbols]
    assert dependency.calls[0] is symbols
    assert result is response
    assert result["quotes"]["AAPL.US"]["last"] == "211.16"  # type: ignore[index]


def test_get_quotes_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_quotes(self, symbols: object) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_quotes(["AAPL.US"])

    assert exc_info.value is original


def test_find_symbol_delegates_without_transforming_query_or_response() -> None:
    query = "Apple Inc"
    response = {
        "items": [
            {
                "ticker": "AAPL.US",
                "price": "211.16",
                "unknown_field": {"nested": [True, None]},
            }
        ]
    }
    dependency = FakeFindSymbolDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.find_symbol(query)

    assert dependency.calls == [query]
    assert dependency.calls[0] is query
    assert result is response
    assert result["items"][0]["price"] == "211.16"  # type: ignore[index]


def test_find_symbol_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def find_symbol(self, query: object) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.find_symbol("Apple")

    assert exc_info.value is original


def test_get_news_delegates_defaults_without_transforming_response() -> None:
    query = "Казахстан"
    response = {"result": {"items": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakeNewsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_news(query)

    assert dependency.calls == [(query, None, None, 30)]
    assert dependency.calls[0][0] is query
    assert result is response


def test_get_news_delegates_explicit_arguments() -> None:
    query = "ignored"
    symbol = "AAPL.US"
    story_id = "story-17"
    limit = 7
    response = {"result": {"items": []}}
    dependency = FakeNewsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_news(
        query,
        symbol=symbol,
        story_id=story_id,
        limit=limit,
    )

    assert dependency.calls == [(query, symbol, story_id, limit)]
    assert result is response


def test_get_news_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_news(
            self,
            query: str,
            *,
            symbol: str | None = None,
            story_id: str | None = None,
            limit: int = 30,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_news("query")

    assert exc_info.value is original


def test_get_candles_delegates_without_transforming_arguments_or_response() -> None:
    symbol = "AAPL.US"
    start = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    end = datetime(2024, 1, 2, 16, 0, tzinfo=UTC)
    timeframe = 3600
    candles = [
        {
            "timestamp": "2024-01-01T09:30:00Z",
            "open": "185.10",
            "high": "186.20",
            "low": "184.90",
            "close": "186.00",
            "unknown_field": {"nested": [True, None]},
        },
        {
            "timestamp": "2024-01-01T10:30:00Z",
            "open": "186.00",
            "high": "187.00",
            "low": "185.80",
            "close": "186.75",
        },
    ]
    response = {"candles": candles}
    dependency = FakeCandlesDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_candles(symbol, start, end, timeframe)

    assert dependency.calls == [(symbol, start, end, timeframe)]
    assert dependency.calls[0][1] is start
    assert dependency.calls[0][2] is end
    assert result is response
    assert result["candles"] is candles
    assert result["candles"][0]["open"] == "185.10"  # type: ignore[index]
    assert result["candles"][0]["timestamp"] == "2024-01-01T09:30:00Z"  # type: ignore[index]


def test_get_candles_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_candles(
            self,
            symbol: object,
            start: object,
            end: object,
            timeframe: object,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_candles(
            "AAPL.US",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
            3600,
        )

    assert exc_info.value is original


def test_market_service_is_public_but_sdk_adapter_is_not() -> None:
    assert broker.MarketService is MarketService
    assert "MarketService" in broker.__all__
    assert "TradernetSdkAdapter" not in broker.__all__
    assert not hasattr(broker, "TradernetSdkAdapter")
