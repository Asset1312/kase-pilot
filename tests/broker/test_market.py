"""Tests for the market-data broker service."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from inspect import signature
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


class FakeSymbolsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_symbols(self, exchange: object = None) -> dict[str, Any]:
        self.calls.append(exchange)
        return self.response


class FakeSymbolDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_symbol(
        self,
        symbol: object,
        lang: object = None,
    ) -> dict[str, Any]:
        self.calls.append((symbol, lang))
        return self.response


class FakeExportSecuritiesDependency:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def export_securities(
        self,
        symbols: object,
        fields: object = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((symbols, fields))
        return self.response


class FakeOptionsDependency:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_options(
        self,
        underlying: object,
        exchange: object,
    ) -> list[dict[str, Any]]:
        self.calls.append((underlying, exchange))
        return self.response


class FakeTariffsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def get_tariffs(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


class FakeSecuritySessionsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def list_security_sessions(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


class FakeOrderFilesDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_order_files(
        self,
        order_id: object,
        internal_id: object,
    ) -> dict[str, Any]:
        self.calls.append((order_id, internal_id))
        return self.response


class FakeUserDataDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def get_user_data(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


class FakeMissingFieldsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def check_missing_fields(
        self,
        step: object,
        office: object,
    ) -> dict[str, Any]:
        self.calls.append((step, office))
        return self.response


class FakeProfileFieldsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_profile_fields(self, reception: object) -> dict[str, Any]:
        self.calls.append(reception)
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


class FakeMarketStatusDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_market_status(
        self,
        market: object = "*",
        *,
        mode: object = None,
    ) -> dict[str, Any]:
        self.calls.append((market, mode))
        return self.response


class FakeMostTradedDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object, object]] = []

    def get_most_traded(
        self,
        instrument_type: object = "stocks",
        *,
        exchange: object = "usa",
        gainers: object = True,
        limit: object = 10,
    ) -> dict[str, Any]:
        self.calls.append((instrument_type, exchange, gainers, limit))
        return self.response


class FakeHistoricalDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_historical(self, start: object, end: object) -> dict[str, Any]:
        self.calls.append((start, end))
        return self.response


class FakeCorporateActionsDependency:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[object] = []

    def corporate_actions(self, reception: object = 35) -> list[dict[str, Any]]:
        self.calls.append(reception)
        return self.response


class FakePriceAlertsDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_price_alerts(self, symbol: object = None) -> dict[str, Any]:
        self.calls.append(symbol)
        return self.response


class FakeRequestsHistoryDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[
            tuple[object, object, object, object, object, object, object]
        ] = []

    def get_requests_history(
        self,
        doc_id: object = None,
        exec_id: object = None,
        start: object = None,
        end: object = None,
        limit: object = None,
        offset: object = None,
        status: object = None,
    ) -> dict[str, Any]:
        self.calls.append((doc_id, exec_id, start, end, limit, offset, status))
        return self.response


class FakeBrokerReportDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object]] = []

    def get_broker_report(
        self,
        *,
        start: object,
        end: object,
        period: object,
    ) -> dict[str, Any]:
        self.calls.append((start, end, period))
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


@pytest.mark.parametrize("exchange", [None, " KASE "])
def test_get_symbols_delegates_and_preserves_response_identity(
    exchange: str | None,
) -> None:
    response = {"result": {"symbols": [{"ticker": "HSBK.KZ"}]}}
    dependency = FakeSymbolsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_symbols(exchange)

    assert dependency.calls == [exchange]
    assert result is response


@pytest.mark.parametrize("lang", [None, " ru "])
def test_get_symbol_delegates_and_preserves_response_identity(
    lang: str | None,
) -> None:
    symbol = " AAPL.US "
    response = {"result": {"ticker": "AAPL.US", "name": "Apple"}}
    dependency = FakeSymbolDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_symbol(symbol, lang)

    assert dependency.calls == [(symbol, lang)]
    assert dependency.calls[0][0] is symbol
    assert dependency.calls[0][1] is lang
    assert result is response


@pytest.mark.parametrize("fields", [None, ["ticker", "ltp"]])
def test_export_securities_delegates_and_preserves_response_identity(
    fields: list[str] | None,
) -> None:
    symbols = ["AAPL", "MSFT"]
    response = [{"ticker": "AAPL"}, {"ticker": "MSFT"}]
    dependency = FakeExportSecuritiesDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.export_securities(symbols, fields)

    assert dependency.calls == [(symbols, fields)]
    assert dependency.calls[0][0] is symbols
    assert dependency.calls[0][1] is fields
    assert result is response


def test_get_options_delegates_and_preserves_response_identity() -> None:
    underlying = " AaPl "
    exchange = " UsA "
    response = [{"ticker": "AAPL.US"}]
    dependency = FakeOptionsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_options(underlying, exchange)

    assert dependency.calls == [(underlying, exchange)]
    assert dependency.calls[0][0] is underlying
    assert dependency.calls[0][1] is exchange
    assert result is response


def test_get_tariffs_delegates_and_preserves_response_identity() -> None:
    response = {"result": {"tariffs": [{"name": "Investor"}]}}
    dependency = FakeTariffsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_tariffs()

    assert dependency.calls == 1
    assert result is response


def test_list_security_sessions_delegates_and_preserves_response_identity() -> None:
    response = {"result": {"sessions": [{"market": "KASE"}]}}
    dependency = FakeSecuritySessionsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.list_security_sessions()

    assert dependency.calls == 1
    assert result is response


@pytest.mark.parametrize(
    ("order_id", "internal_id"),
    [(17, None), (None, 23), (17, 23)],
)
def test_get_order_files_delegates_and_preserves_response_identity(
    order_id: int | None,
    internal_id: int | None,
) -> None:
    response = {"result": {"files": [{"name": "document.pdf"}]}}
    dependency = FakeOrderFilesDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_order_files(order_id, internal_id)

    assert dependency.calls == [(order_id, internal_id)]
    assert result is response


def test_get_user_data_delegates_and_preserves_response_identity() -> None:
    response = {"result": {"portfolio": {"name": "Инвестор"}}}
    dependency = FakeUserDataDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_user_data()

    assert dependency.calls == 1
    assert result is response


def test_check_missing_fields_delegates_and_preserves_response_identity() -> None:
    step = 3
    office = " Almaty "
    response = {"result": {"not_completed": [{"name": "address"}]}}
    dependency = FakeMissingFieldsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.check_missing_fields(step, office)

    assert dependency.calls == [(step, office)]
    assert dependency.calls[0][1] is office
    assert result is response


def test_get_profile_fields_delegates_and_preserves_response_identity() -> None:
    reception = 17
    response = {"result": {"fields": [{"name": "address"}]}}
    dependency = FakeProfileFieldsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_profile_fields(reception)

    assert dependency.calls == [reception]
    assert result is response


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


def test_get_market_status_delegates_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"markets": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakeMarketStatusDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_market_status()

    assert dependency.calls == [("*", None)]
    assert result is response


def test_get_market_status_delegates_explicit_arguments() -> None:
    market = "KASE"
    mode = "demo"
    response = {"result": {"markets": []}}
    dependency = FakeMarketStatusDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_market_status(market, mode=mode)

    assert dependency.calls == [(market, mode)]
    assert dependency.calls[0][0] is market
    assert dependency.calls[0][1] is mode
    assert result is response


def test_get_market_status_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_market_status(
            self,
            market: str = "*",
            *,
            mode: str | None = None,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_market_status()

    assert exc_info.value is original


def test_get_most_traded_delegates_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"items": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakeMostTradedDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_most_traded()

    assert dependency.calls == [("stocks", "usa", True, 10)]
    assert result is response


def test_get_most_traded_delegates_explicit_arguments() -> None:
    instrument_type = "bonds"
    exchange = "europe"
    gainers = False
    limit = 25
    response = {"result": {"items": []}}
    dependency = FakeMostTradedDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_most_traded(
        instrument_type,
        exchange=exchange,
        gainers=gainers,
        limit=limit,
    )

    assert dependency.calls == [(instrument_type, exchange, gainers, limit)]
    assert dependency.calls[0][0] is instrument_type
    assert dependency.calls[0][1] is exchange
    assert dependency.calls[0][2] is gainers
    assert dependency.calls[0][3] is limit
    assert result is response


def test_get_most_traded_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_most_traded(
            self,
            instrument_type: str = "stocks",
            *,
            exchange: str = "usa",
            gainers: bool = True,
            limit: int = 10,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_most_traded()

    assert exc_info.value is original


def test_get_historical_delegates_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"orders": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakeHistoricalDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]
    parameters = signature(MarketService.get_historical).parameters

    result = service.get_historical()

    assert dependency.calls == [
        (parameters["start"].default, parameters["end"].default)
    ]
    assert result is response


def test_get_historical_delegates_explicit_datetimes_unchanged() -> None:
    start = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    end = datetime(2024, 2, 1, 16, 0, tzinfo=UTC)
    dependency = FakeHistoricalDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_historical(start, end)

    assert dependency.calls == [(start, end)]
    assert dependency.calls[0][0] is start
    assert dependency.calls[0][1] is end


def test_get_historical_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_historical(self, start: datetime, end: datetime) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_historical()

    assert exc_info.value is original


def test_corporate_actions_delegates_default_and_preserves_list_identity() -> None:
    response = [{"id": "action-1", "unknown": {"nested": [True, None]}}]
    dependency = FakeCorporateActionsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.corporate_actions()

    assert dependency.calls == [35]
    assert result is response


def test_corporate_actions_delegates_explicit_reception_unchanged() -> None:
    reception = 17
    dependency = FakeCorporateActionsDependency([])
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.corporate_actions(reception)

    assert dependency.calls == [reception]
    assert dependency.calls[0] is reception


def test_corporate_actions_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def corporate_actions(
            self,
            reception: int = 35,
        ) -> list[dict[str, Any]]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.corporate_actions()

    assert exc_info.value is original


def test_get_price_alerts_delegates_none_and_preserves_response_identity() -> None:
    response = {"result": {"alerts": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakePriceAlertsDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_price_alerts()

    assert dependency.calls == [None]
    assert result is response


def test_get_price_alerts_delegates_explicit_symbol_unchanged() -> None:
    symbol = " Aapl.US "
    dependency = FakePriceAlertsDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_price_alerts(symbol)

    assert dependency.calls == [symbol]
    assert dependency.calls[0] is symbol


def test_get_price_alerts_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_price_alerts(
            self,
            symbol: str | None = None,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_price_alerts()

    assert exc_info.value is original


def test_get_requests_history_forwards_defaults_and_preserves_identity() -> None:
    response = {"result": {"requests": [{"unknown": {"nested": [True, None]}}]}}
    dependency = FakeRequestsHistoryDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]
    parameters = signature(MarketService.get_requests_history).parameters

    result = service.get_requests_history()

    assert dependency.calls == [
        (
            None,
            None,
            parameters["start"].default,
            parameters["end"].default,
            None,
            None,
            None,
        )
    ]
    assert result is response


def test_get_requests_history_forwards_all_explicit_arguments_unchanged() -> None:
    doc_id = 17
    exec_id = 23
    start = date(2026, 1, 1)
    end = date(2026, 2, 1)
    limit = 50
    offset = 10
    status = 3
    dependency = FakeRequestsHistoryDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_requests_history(
        doc_id,
        exec_id,
        start,
        end,
        limit,
        offset,
        status,
    )

    assert dependency.calls == [(doc_id, exec_id, start, end, limit, offset, status)]
    assert dependency.calls[0][2] is start
    assert dependency.calls[0][3] is end


def test_get_requests_history_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_requests_history(
            self,
            doc_id: int | None,
            exec_id: int | None,
            start: date,
            end: date,
            limit: int | None,
            offset: int | None,
            status: int | None,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_requests_history()

    assert exc_info.value is original


def test_get_broker_report_forwards_defaults_and_preserves_identity() -> None:
    response = {"trades": [{"unknown": {"nested": [True, None]}}]}
    dependency = FakeBrokerReportDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]
    parameters = signature(MarketService.get_broker_report).parameters

    result = service.get_broker_report()

    assert dependency.calls == [
        (
            parameters["start"].default,
            parameters["end"].default,
            parameters["period"].default,
        )
    ]
    assert result is response


def test_get_broker_report_forwards_explicit_arguments_unchanged() -> None:
    start = "2026-01-01"
    end = date(2026, 1, 31)
    period = time(18, 30, 15)
    dependency = FakeBrokerReportDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_broker_report(start=start, end=end, period=period)

    assert dependency.calls == [(start, end, period)]
    assert dependency.calls[0][0] is start
    assert dependency.calls[0][1] is end
    assert dependency.calls[0][2] is period


def test_get_broker_report_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_broker_report(
            self,
            *,
            start: str | date,
            end: str | date,
            period: time,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_broker_report()

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
