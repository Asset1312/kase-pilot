"""Tests for the internal Tradernet SDK adapter."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime, time
from inspect import signature
from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker._tradernet_sdk import (
    TradernetSdkAdapter,
    _require_list,
    _require_mapping,
)
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class FakeSdkClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []
        self.quote_calls: list[object] = []
        self.find_symbol_calls: list[object] = []
        self.symbol_calls: list[tuple[object, ...]] = []
        self.symbols_calls: list[tuple[object, ...]] = []
        self.export_securities_calls: list[tuple[object, ...]] = []
        self.get_options_calls: list[tuple[object, object]] = []
        self.get_tariffs_list_calls = 0
        self.list_security_sessions_calls = 0
        self.get_order_files_calls: list[tuple[object, object]] = []
        self.get_user_data_calls = 0
        self.check_missing_fields_calls: list[tuple[object, object]] = []
        self.get_profile_fields_calls: list[object] = []
        self.get_news_calls: list[tuple[object, object, object, object]] = []
        self.get_market_status_calls: list[tuple[object, object]] = []
        self.get_most_traded_calls: list[tuple[object, object, object, object]] = []
        self.get_historical_calls: list[tuple[object, object]] = []
        self.corporate_actions_calls: list[object] = []
        self.get_price_alerts_calls: list[object] = []
        self.get_requests_history_calls: list[
            tuple[object, object, object, object, object, object, object]
        ] = []
        self.get_broker_report_calls: list[tuple[object, object, object]] = []
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

    def symbols(self, *args: object) -> Any:
        self.symbols_calls.append(args)
        return self.response

    def symbol(self, *args: object) -> Any:
        self.symbol_calls.append(args)
        return self.response

    def export_securities(self, *args: object) -> Any:
        self.export_securities_calls.append(args)
        return self.response

    def get_options(self, underlying: object, exchange: object) -> Any:
        self.get_options_calls.append((underlying, exchange))
        return self.response

    def get_tariffs_list(self) -> Any:
        self.get_tariffs_list_calls += 1
        return self.response

    def list_security_sessions(self) -> Any:
        self.list_security_sessions_calls += 1
        return self.response

    def get_order_files(self, order_id: object, internal_id: object) -> Any:
        self.get_order_files_calls.append((order_id, internal_id))
        return self.response

    def get_user_data(self) -> Any:
        self.get_user_data_calls += 1
        return self.response

    def check_missing_fields(self, step: object, office: object) -> Any:
        self.check_missing_fields_calls.append((step, office))
        return self.response

    def get_profile_fields(self, reception: object) -> Any:
        self.get_profile_fields_calls.append(reception)
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

    def get_historical(self, start: object, end: object) -> Any:
        self.get_historical_calls.append((start, end))
        return self.response

    def corporate_actions(self, reception: object = 35) -> Any:
        self.corporate_actions_calls.append(reception)
        return self.response

    def get_price_alerts(self, symbol: object = None) -> Any:
        self.get_price_alerts_calls.append(symbol)
        return self.response

    def get_requests_history(
        self,
        doc_id: object = None,
        exec_id: object = None,
        start: object = None,
        end: object = None,
        limit: object = None,
        offset: object = None,
        status: object = None,
    ) -> Any:
        self.get_requests_history_calls.append(
            (doc_id, exec_id, start, end, limit, offset, status)
        )
        return self.response

    def get_broker_report(
        self,
        *,
        start: object,
        end: object,
        period: object,
    ) -> Any:
        self.get_broker_report_calls.append((start, end, period))
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


def test_require_mapping_preserves_mapping_identity() -> None:
    response = {"result": {"nested": [True, None]}}

    assert _require_mapping(response, "test") is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_require_mapping_rejects_non_mapping(response: object) -> None:
    with pytest.raises(ValidationError, match="non-mapping test response"):
        _require_mapping(response, "test")


def test_require_list_preserves_list_identity() -> None:
    response = [{"unknown": {"nested": [True, None]}}]

    assert _require_list(response, "test") is response


@pytest.mark.parametrize(
    "response",
    [
        (),
        "not a list",
        {"result": []},
    ],
)
def test_require_list_rejects_other_top_level_shapes(response: object) -> None:
    with pytest.raises(ValidationError, match="non-list test response"):
        _require_list(response, "test")


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


def test_get_symbols_omits_exchange_and_preserves_response_identity() -> None:
    response = {"result": {"symbols": [{"ticker": "HSBK.KZ"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_symbols()

    assert sdk_client.symbols_calls == [()]
    assert result is response


def test_get_symbols_forwards_explicit_exchange_unchanged() -> None:
    exchange = " KASE "
    sdk_client = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    adapter.get_symbols(exchange)

    assert sdk_client.symbols_calls == [(exchange,)]
    assert sdk_client.symbols_calls[0][0] is exchange


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_symbols_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping symbols response"):
        adapter.get_symbols()


def test_get_symbol_omits_lang_and_preserves_response_identity() -> None:
    symbol = " AAPL.US "
    response = {"result": {"ticker": "AAPL.US", "name": "Apple"}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_symbol(symbol)

    assert sdk_client.symbol_calls == [(symbol,)]
    assert sdk_client.symbol_calls[0][0] is symbol
    assert result is response


def test_get_symbol_forwards_explicit_lang_unchanged() -> None:
    symbol = "AAPL.US"
    lang = " ru "
    sdk_client = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    adapter.get_symbol(symbol, lang)

    assert sdk_client.symbol_calls == [(symbol, lang)]
    assert sdk_client.symbol_calls[0][0] is symbol
    assert sdk_client.symbol_calls[0][1] is lang


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_symbol_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping symbol response"):
        adapter.get_symbol("AAPL.US")


def test_export_securities_omits_fields_and_preserves_response_identity() -> None:
    symbols = ["AAPL"]
    response = [{"ticker": "AAPL", "name": "Apple"}]
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.export_securities(symbols)

    assert sdk_client.export_securities_calls == [(symbols,)]
    assert sdk_client.export_securities_calls[0][0] is symbols
    assert result is response


def test_export_securities_forwards_symbols_and_fields_in_order() -> None:
    symbols = ["AAPL", "MSFT"]
    fields = ["ticker", "ltp", "currency"]
    sdk_client = FakeSdkClient([])
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    adapter.export_securities(symbols, fields)

    assert sdk_client.export_securities_calls == [(symbols, fields)]
    assert sdk_client.export_securities_calls[0][0] is symbols
    assert sdk_client.export_securities_calls[0][1] is fields


@pytest.mark.parametrize("response", [None, {}, (), "not a list", 42])
def test_export_securities_rejects_non_list_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-list securities export response"):
        adapter.export_securities(["AAPL"])


def test_get_options_forwards_arguments_and_preserves_response_identity() -> None:
    underlying = " AaPl "
    exchange = " UsA "
    response = [{"ticker": "AAPL.US", "strike": 200}]
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_options(underlying, exchange)

    assert sdk_client.get_options_calls == [(underlying, exchange)]
    assert sdk_client.get_options_calls[0][0] is underlying
    assert sdk_client.get_options_calls[0][1] is exchange
    assert result is response


@pytest.mark.parametrize("response", [None, {}, (), "not a list", 42])
def test_get_options_rejects_non_list_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-list options response"):
        adapter.get_options("AAPL", "usa")


def test_get_tariffs_delegates_once_and_preserves_response_identity() -> None:
    response = {"result": {"tariffs": [{"name": "Investor"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_tariffs()

    assert sdk_client.get_tariffs_list_calls == 1
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_tariffs_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping tariffs response"):
        adapter.get_tariffs()


def test_list_security_sessions_delegates_once_and_preserves_response_identity() -> (
    None
):
    response = {"result": {"sessions": [{"market": "KASE"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.list_security_sessions()

    assert sdk_client.list_security_sessions_calls == 1
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_list_security_sessions_rejects_non_mapping_response(
    response: object,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping security sessions response"):
        adapter.list_security_sessions()


@pytest.mark.parametrize(
    ("order_id", "internal_id"),
    [(17, None), (None, 23), (17, 23)],
)
def test_get_order_files_forwards_identifiers_and_preserves_response_identity(
    order_id: int | None,
    internal_id: int | None,
) -> None:
    response = {"result": {"files": [{"name": "document.pdf"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_order_files(order_id, internal_id)

    assert sdk_client.get_order_files_calls == [(order_id, internal_id)]
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_order_files_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping order files response"):
        adapter.get_order_files(17, None)


def test_get_user_data_delegates_once_and_preserves_response_identity() -> None:
    response = {"result": {"portfolio": {"name": "Инвестор"}}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_user_data()

    assert sdk_client.get_user_data_calls == 1
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_user_data_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping user data response"):
        adapter.get_user_data()


def test_check_missing_fields_forwards_arguments_and_preserves_response_identity() -> (
    None
):
    step = 3
    office = " Almaty "
    response = {"result": {"not_completed": [{"name": "address"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.check_missing_fields(step, office)

    assert sdk_client.check_missing_fields_calls == [(step, office)]
    assert sdk_client.check_missing_fields_calls[0][1] is office
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_check_missing_fields_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping missing fields response"):
        adapter.check_missing_fields(3, "Almaty")


def test_get_profile_fields_forwards_reception_and_preserves_response_identity() -> (
    None
):
    reception = 17
    response = {"result": {"fields": [{"name": "address"}]}}
    sdk_client = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk_client)  # type: ignore[arg-type]

    result = adapter.get_profile_fields(reception)

    assert sdk_client.get_profile_fields_calls == [reception]
    assert result is response


@pytest.mark.parametrize("response", [None, [], (), "not a mapping", 42])
def test_get_profile_fields_rejects_non_mapping_response(response: object) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping profile fields response"):
        adapter.get_profile_fields(17)


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


def test_get_historical_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"orders": [{"unknown": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]
    parameters = signature(TradernetSdkAdapter.get_historical).parameters

    result = adapter.get_historical()

    assert sdk.get_historical_calls == [
        (parameters["start"].default, parameters["end"].default)
    ]
    assert result is response


def test_get_historical_forwards_explicit_arguments_unchanged() -> None:
    start = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    end = datetime(2024, 2, 1, 16, 0, tzinfo=UTC)
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_historical(start, end)

    assert sdk.get_historical_calls == [(start, end)]
    assert sdk.get_historical_calls[0][0] is start
    assert sdk.get_historical_calls[0][1] is end


@pytest.mark.parametrize("response", [None, [], "not a mapping", 42])
def test_get_historical_non_mapping_response_raises_validation_error(
    response: Any,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping historical orders response"):
        adapter.get_historical()


def test_get_historical_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_historical(
            self,
            start: datetime = datetime(2011, 1, 11),  # noqa: DTZ001
            end: datetime = datetime.now(),  # noqa: B008, DTZ005
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_historical()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_corporate_actions_forwards_default_and_preserves_list_identity() -> None:
    response = [{"id": "action-1", "unknown": {"nested": [True, None]}}]
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.corporate_actions()

    assert sdk.corporate_actions_calls == [35]
    assert result is response


def test_corporate_actions_forwards_explicit_reception_unchanged() -> None:
    reception = 17
    sdk = FakeSdkClient([])
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.corporate_actions(reception)

    assert sdk.corporate_actions_calls == [reception]
    assert sdk.corporate_actions_calls[0] is reception


@pytest.mark.parametrize(
    "response",
    [
        None,
        (),
        "not a list",
        {"result": []},
        42,
    ],
)
def test_corporate_actions_non_list_response_raises_validation_error(
    response: object,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-list corporate actions response"):
        adapter.corporate_actions()


def test_corporate_actions_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def corporate_actions(self, reception: int = 35) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.corporate_actions()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_price_alerts_forwards_default_and_preserves_mapping_identity() -> None:
    response = {"result": {"alerts": [{"unknown": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    result = adapter.get_price_alerts()

    assert sdk.get_price_alerts_calls == [None]
    assert result is response


def test_get_price_alerts_forwards_explicit_symbol_unchanged() -> None:
    symbol = " Aapl.US "
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_price_alerts(symbol)

    assert sdk.get_price_alerts_calls == [symbol]
    assert sdk.get_price_alerts_calls[0] is symbol


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        (),
        "not a mapping",
        42,
    ],
)
def test_get_price_alerts_non_mapping_response_raises_validation_error(
    response: object,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping price alerts response"):
        adapter.get_price_alerts()


def test_get_price_alerts_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_price_alerts(self, symbol: str | None = None) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_price_alerts()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_requests_history_forwards_defaults_and_preserves_mapping_identity() -> (
    None
):
    response = {"result": {"requests": [{"unknown": {"nested": [True, None]}}]}}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]
    parameters = signature(TradernetSdkAdapter.get_requests_history).parameters

    result = adapter.get_requests_history()

    assert sdk.get_requests_history_calls == [
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
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_requests_history(
        doc_id,
        exec_id,
        start,
        end,
        limit,
        offset,
        status,
    )

    assert sdk.get_requests_history_calls == [
        (doc_id, exec_id, start, end, limit, offset, status)
    ]
    assert sdk.get_requests_history_calls[0][2] is start
    assert sdk.get_requests_history_calls[0][3] is end


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        (),
        "not a mapping",
        42,
    ],
)
def test_get_requests_history_non_mapping_response_raises_validation_error(
    response: object,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping requests history response"):
        adapter.get_requests_history()


def test_get_requests_history_sdk_exception_becomes_api_request_error_with_cause() -> (
    None
):
    original = RuntimeError("SDK failure")

    class FailingSdkClient:
        def get_requests_history(
            self,
            doc_id: int | None = None,
            exec_id: int | None = None,
            start: date = datetime(2011, 1, 11),  # noqa: DTZ001
            end: date = datetime.now(),  # noqa: B008, DTZ005
            limit: int | None = None,
            offset: int | None = None,
            status: int | None = None,
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_requests_history()

    assert exc_info.value.__cause__ is original
    assert "SDK failure" not in str(exc_info.value)


def test_get_broker_report_forwards_defaults_once_and_preserves_identity() -> None:
    response = {"trades": [{"unknown": {"nested": [True, None]}}]}
    sdk = FakeSdkClient(response)
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]
    parameters = signature(TradernetSdkAdapter.get_broker_report).parameters

    result = adapter.get_broker_report()

    assert sdk.get_broker_report_calls == [
        (
            parameters["start"].default,
            parameters["end"].default,
            parameters["period"].default,
        )
    ]
    assert result is response


def test_get_broker_report_forwards_representative_values_unchanged() -> None:
    start = "2026-01-01"
    end = date(2026, 1, 31)
    period = time(18, 30, 15)
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_broker_report(start=start, end=end, period=period)

    assert sdk.get_broker_report_calls == [(start, end, period)]
    assert sdk.get_broker_report_calls[0][0] is start
    assert sdk.get_broker_report_calls[0][1] is end
    assert sdk.get_broker_report_calls[0][2] is period


def test_get_broker_report_preserves_start_and_end_date_identity() -> None:
    start = date(2026, 1, 1)
    end = date(2026, 1, 31)
    sdk = FakeSdkClient({})
    adapter = TradernetSdkAdapter(sdk)  # type: ignore[arg-type]

    adapter.get_broker_report(start=start, end=end)

    assert sdk.get_broker_report_calls[0][0] is start
    assert sdk.get_broker_report_calls[0][1] is end


@pytest.mark.parametrize(
    "response",
    [
        [],
        (),
        "not a mapping",
        42,
        None,
    ],
)
def test_get_broker_report_non_mapping_response_raises_validation_error(
    response: object,
) -> None:
    adapter = TradernetSdkAdapter(FakeSdkClient(response))  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping broker report response"):
        adapter.get_broker_report()


def test_get_broker_report_sdk_exception_becomes_api_request_error_with_cause() -> None:
    original = KeyError("report")

    class FailingSdkClient:
        def get_broker_report(
            self,
            *,
            start: str | date = date(1970, 1, 1),
            end: str | date = date.today(),  # noqa: B008, DTZ011
            period: time = time(23, 59, 59),
        ) -> Any:
            raise original

    adapter = TradernetSdkAdapter(FailingSdkClient())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        adapter.get_broker_report()

    assert exc_info.value.__cause__ is original
    assert "report" not in str(exc_info.value)


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
