"""Tests for the internal Tradernet SDK adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class FakeSdkClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []
        self.quote_calls: list[object] = []
        self.find_symbol_calls: list[object] = []
        self.get_news_calls: list[tuple[object, object, object, object]] = []
        self.get_market_status_calls: list[tuple[object, object]] = []
        self.get_most_traded_calls: list[tuple[object, object, object, object]] = []
        self.candle_calls: list[tuple[object, object, object, object]] = []
        self.user_info_calls = 0
        self.account_summary_calls = 0
        self.get_placed_calls: list[bool] = []
        self.get_trades_history_calls: list[
            tuple[object, object, dict[str, object]]
        ] = []

    def security_info(self, ticker: str, *, sup: bool = True) -> Any:
        self.calls.append((ticker, sup))
        return self.response

    def get_quotes(self, symbols: object) -> Any:
        self.quote_calls.append(symbols)
        return self.response

    def find_symbol(self, query: object) -> Any:
        self.find_symbol_calls.append(query)
        return self.response

    def get_news(
        self,
        query: object,
        *,
        symbol: object = None,
        story_id: object = None,
        limit: object = 30,
    ) -> Any:
        self.get_news_calls.append((query, symbol, story_id, limit))
        return self.response

    def get_market_status(
        self,
        market: object = "*",
        *,
        mode: object = None,
    ) -> Any:
        self.get_market_status_calls.append((market, mode))
        return self.response

    def get_most_traded(
        self,
        instrument_type: object = "stocks",
        *,
        exchange: object = "usa",
        gainers: object = True,
        limit: object = 10,
    ) -> Any:
        self.get_most_traded_calls.append((instrument_type, exchange, gainers, limit))
        return self.response

    def get_candles(
        self,
        symbol: object,
        start: object,
        end: object,
        timeframe: object,
    ) -> Any:
        self.candle_calls.append((symbol, start, end, timeframe))
        return self.response

    def user_info(self) -> Any:
        self.user_info_calls += 1
        return self.response

    def account_summary(self) -> Any:
        self.account_summary_calls += 1
        return self.response

    def get_placed(self, *, active: bool = True) -> Any:
        self.get_placed_calls.append(active)
        return self.response

    def get_trades_history(
        self,
        start: object,
        end: object,
        **kwargs: object,
    ) -> Any:
        self.get_trades_history_calls.append((start, end, kwargs))
        return self.response


def test_calls_security_info_once_with_ticker_and_sup() -> None:
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_security_info("AAPL.US", sup=False)

    assert sdk.calls == [("AAPL.US", False)]


def test_returns_separate_dict_without_filtering_or_conversion() -> None:
    original: Mapping[str, Any] = {
        "nt_ticker": "AAPL.US",
        "min_step": "0.01",
        "lot": "1",
        "unknown_field": {"nested": True},
    }
    adapter = TradernetSdkAdapter(FakeSdkClient(original))  # type: ignore[arg-type]

    result = adapter.get_security_info("AAPL.US")

    assert type(result) is dict
    assert result == original
    assert result["min_step"] == "0.01"
    assert result["lot"] == "1"
    assert "unknown_field" in result
    assert "mrkt" not in result
    result["nt_ticker"] = "changed"
    assert original["nt_ticker"] == "AAPL.US"


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_non_mapping_response_raises_validation_error(response: Any) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping"):
        adapter.get_security_info("AAPL.US")


def test_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def security_info(self, ticker: str, *, sup: bool = True) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_security_info("AAPL.US")

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


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
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_quotes(symbols)

    assert sdk.quote_calls == [symbols]
    assert sdk.quote_calls[0] is symbols
    assert result is response
    assert result["quotes"]["AAPL.US"]["last"] == "211.16"  # type: ignore[index]


def test_get_quotes_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_quotes(self, symbols: object) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_quotes(["AAPL.US"])

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


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
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.find_symbol(query)

    assert sdk.find_symbol_calls == [query]
    assert sdk.find_symbol_calls[0] is query
    assert result is response
    assert result["items"][0]["price"] == "211.16"  # type: ignore[index]


def test_find_symbol_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def find_symbol(self, query: object) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.find_symbol("Apple")

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_news_forwards_query_and_sdk_defaults_without_transforming_response() -> (
    None
):
    query = "Казахстан"
    response = {"result": {"items": [{"unknown_field": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_news(query)

    assert sdk.get_news_calls == [(query, None, None, 30)]
    assert sdk.get_news_calls[0][0] is query
    assert result is response


def test_get_news_forwards_explicit_optional_arguments() -> None:
    query = "ignored query"
    symbol = "AAPL.US"
    story_id = "story-17"
    limit = 7
    response = {"result": {"items": []}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_news(
        query,
        symbol=symbol,
        story_id=story_id,
        limit=limit,
    )

    assert sdk.get_news_calls == [(query, symbol, story_id, limit)]
    assert sdk.get_news_calls[0][1] is symbol
    assert sdk.get_news_calls[0][2] is story_id
    assert sdk.get_news_calls[0][3] is limit
    assert result is response


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_news_non_mapping_response_raises_validation_error(response: Any) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping news response"):
        adapter.get_news("query")


def test_get_news_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_news(
            self,
            query: str,
            *,
            symbol: str | None = None,
            story_id: str | None = None,
            limit: int = 30,
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_news("query")

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_market_status_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"markets": [{"unknown": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_market_status()

    assert sdk.get_market_status_calls == [("*", None)]
    assert result is response


def test_get_market_status_forwards_explicit_market() -> None:
    market = "KASE"
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_market_status(market)

    assert sdk.get_market_status_calls == [(market, None)]
    assert sdk.get_market_status_calls[0][0] is market


def test_get_market_status_forwards_explicit_mode() -> None:
    market = "KASE"
    mode = "demo"
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_market_status(market, mode=mode)

    assert sdk.get_market_status_calls == [(market, mode)]
    assert sdk.get_market_status_calls[0][0] is market
    assert sdk.get_market_status_calls[0][1] is mode


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_market_status_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping market status response"):
        adapter.get_market_status()


def test_get_market_status_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_market_status(
            self,
            market: str = "*",
            *,
            mode: str | None = None,
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_market_status()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_most_traded_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"items": [{"unknown": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_most_traded()

    assert sdk.get_most_traded_calls == [("stocks", "usa", True, 10)]
    assert result is response


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ({"instrument_type": "bonds"}, ("bonds", "usa", True, 10)),
        ({"exchange": "europe"}, ("stocks", "europe", True, 10)),
        ({"gainers": False}, ("stocks", "usa", False, 10)),
        ({"limit": 25}, ("stocks", "usa", True, 25)),
    ],
)
def test_get_most_traded_forwards_each_explicit_argument(
    arguments: dict[str, Any],
    expected: tuple[object, object, object, object],
) -> None:
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_most_traded(**arguments)

    assert sdk.get_most_traded_calls == [expected]


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_most_traded_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping most-traded response"):
        adapter.get_most_traded()


def test_get_most_traded_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_most_traded(
            self,
            instrument_type: str = "stocks",
            *,
            exchange: str = "usa",
            gainers: bool = True,
            limit: int = 10,
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_most_traded()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


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
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_candles(symbol, start, end, timeframe)

    assert sdk.candle_calls == [(symbol, start, end, timeframe)]
    assert sdk.candle_calls[0][1] is start
    assert sdk.candle_calls[0][2] is end
    assert result is response
    assert result["candles"] is candles
    assert result["candles"][0]["open"] == "185.10"  # type: ignore[index]
    assert result["candles"][0]["timestamp"] == "2024-01-01T09:30:00Z"  # type: ignore[index]


def test_get_candles_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_candles(
            self,
            symbol: object,
            start: object,
            end: object,
            timeframe: object,
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_candles(
            "AAPL.US",
            datetime(2024, 1, 1, tzinfo=UTC),
            datetime(2024, 1, 2, tzinfo=UTC),
            3600,
        )

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_user_info_delegates_without_transforming_response() -> None:
    nested = {"positions": [{"quantity": "12.50", "value": None}]}
    response = {
        "account": nested,
        "unknown_field": [True, {"currency": "KZT"}],
    }
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.user_info()

    assert sdk.user_info_calls == 1
    assert result is response
    assert result["account"] is nested
    assert result["account"]["positions"][0]["quantity"] == "12.50"  # type: ignore[index]
    assert result["account"]["positions"][0]["value"] is None  # type: ignore[index]
    assert result["unknown_field"] is response["unknown_field"]


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_user_info_non_mapping_response_raises_validation_error(response: Any) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping"):
        adapter.user_info()


def test_user_info_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def user_info(self) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.user_info()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_account_summary_delegates_without_transforming_response() -> None:
    positions = [{"ticker": "AAPL.US", "quantity": "12.50"}]
    response = {
        "positions": positions,
        "unknown_field": {"nested": [True, None]},
    }
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.account_summary()

    assert sdk.account_summary_calls == 1
    assert result is response
    assert result["positions"] is positions
    assert result["unknown_field"] is response["unknown_field"]
    assert result["positions"][0]["quantity"] == "12.50"  # type: ignore[index]


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_account_summary_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping"):
        adapter.account_summary()


def test_account_summary_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def account_summary(self) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.account_summary()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_placed_uses_default_active_and_preserves_response_identity() -> None:
    orders = [{"id": 17, "price": "211.16"}]
    response = {
        "orders": orders,
        "unknown_field": {"nested": [True, None]},
    }
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_placed()

    assert sdk.get_placed_calls == [True]
    assert result is response
    assert result["orders"] is orders
    assert result["unknown_field"] is response["unknown_field"]
    assert result["orders"][0]["price"] == "211.16"  # type: ignore[index]


def test_get_placed_passes_false_active() -> None:
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_placed(active=False)

    assert sdk.get_placed_calls == [False]


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_placed_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping"):
        adapter.get_placed()


def test_get_placed_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_placed(self, *, active: bool = True) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_placed()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_trades_history_delegates_dates_and_preserves_response_identity() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    trades = [{"id": 17, "price": "211.16"}]
    response = {
        "trades": trades,
        "unknown_field": {"nested": [True, None]},
    }
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_trades_history(start, end)

    assert sdk.get_trades_history_calls == [(start, end, {})]
    assert sdk.get_trades_history_calls[0][0] is start
    assert sdk.get_trades_history_calls[0][1] is end
    assert result is response
    assert result["trades"] is trades
    assert result["unknown_field"] is response["unknown_field"]


def test_get_trades_history_passes_symbol_without_normalizing_it() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_trades_history(start, end, symbol=symbol)

    assert sdk.get_trades_history_calls == [
        (start, end, {"symbol": symbol}),
    ]
    assert sdk.get_trades_history_calls[0][0] is start
    assert sdk.get_trades_history_calls[0][1] is end
    assert sdk.get_trades_history_calls[0][2]["symbol"] is symbol


@pytest.mark.parametrize("limit", [0, -1, 10**100, True])
def test_get_trades_history_passes_limit_without_validation(limit: int) -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_trades_history(start, end, limit=limit)

    assert sdk.get_trades_history_calls == [
        (start, end, {"limit": limit}),
    ]
    assert sdk.get_trades_history_calls[0][2]["limit"] is limit


def test_get_trades_history_passes_symbol_and_limit_together() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    limit = 250
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_trades_history(start, end, symbol=symbol, limit=limit)

    assert sdk.get_trades_history_calls == [
        (start, end, {"symbol": symbol, "limit": limit}),
    ]
    assert sdk.get_trades_history_calls[0][2]["symbol"] is symbol
    assert sdk.get_trades_history_calls[0][2]["limit"] is limit


@pytest.mark.parametrize(
    ("symbol", "limit", "currency", "expected_kwargs"),
    [
        (None, None, "  uSd  ", {"currency": "  uSd  "}),
        (None, None, "", {"currency": ""}),
        ("AAPL.US", None, "USD", {"symbol": "AAPL.US", "currency": "USD"}),
        (None, 250, "USD", {"limit": 250, "currency": "USD"}),
        (
            "AAPL.US",
            250,
            "USD",
            {"symbol": "AAPL.US", "limit": 250, "currency": "USD"},
        ),
    ],
)
def test_get_trades_history_passes_currency_without_normalizing_it(
    symbol: str | None,
    limit: int | None,
    currency: str,
    expected_kwargs: dict[str, object],
) -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_trades_history(
        start,
        end,
        symbol=symbol,
        limit=limit,
        currency=currency,
    )

    assert sdk.get_trades_history_calls == [(start, end, expected_kwargs)]
    assert sdk.get_trades_history_calls[0][2]["currency"] is currency


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_trades_history_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping"):
        adapter.get_trades_history(date(2025, 1, 1), date(2025, 2, 1))


def test_get_trades_history_sdk_exception_becomes_api_request_error_with_cause() -> (
    None
):
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_trades_history(self, start: object, end: object) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_trades_history(date(2025, 1, 1), date(2025, 2, 1))

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_broker_public_exports_include_account_service() -> None:
    assert broker.__all__ == [
        "AccountService",
        "BrokerClient",
        "MarketService",
        "OrdersService",
        "PortfolioService",
        "ReportsService",
    ]
    assert "TradernetSdkAdapter" not in broker.__all__
    assert not hasattr(broker, "TradernetSdkAdapter")
