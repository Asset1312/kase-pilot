"""Tests for application composition."""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from kase_pilot import app
from kase_pilot.application import (
    CheckMissingFields,
    ExportSecurities,
    FindInstrument,
    GetAccountSummary,
    GetBrokerReport,
    GetCorporateActions,
    GetCurrentQuotes,
    GetHistorical,
    GetHistoricalCandles,
    GetMarketStatus,
    GetMostTraded,
    GetNews,
    GetOptions,
    GetOrderFiles,
    GetPlacedOrders,
    GetPriceAlerts,
    GetProfileFields,
    GetRequestsHistory,
    GetSecurityInfo,
    GetSymbol,
    GetSymbols,
    GetTariffs,
    GetTradesHistory,
    GetUserData,
    GetUserInfo,
    ListSecuritySessions,
)
from kase_pilot.broker import AccountService, MarketService
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter


class FakeSdkClient:
    pass


def test_create_check_missing_fields_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def check_missing_fields(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_check_missing_fields("public-value", "private-value")

    assert isinstance(use_case, CheckMissingFields)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_profile_fields_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_profile_fields(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_profile_fields("public-value", "private-value")

    assert isinstance(use_case, GetProfileFields)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_export_securities_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def export_securities(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_export_securities("public-value", "private-value")

    assert isinstance(use_case, ExportSecurities)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_options_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_options(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_options("public-value", "private-value")

    assert isinstance(use_case, GetOptions)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_tariffs_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_tariffs_list(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_tariffs("public-value", "private-value")

    assert isinstance(use_case, GetTariffs)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_list_security_sessions_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def list_security_sessions(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_list_security_sessions("public-value", "private-value")

    assert isinstance(use_case, ListSecuritySessions)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_order_files_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_order_files(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_order_files("public-value", "private-value")

    assert isinstance(use_case, GetOrderFiles)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_user_data_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_user_data(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_user_data("public-value", "private-value")

    assert isinstance(use_case, GetUserData)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_account_summary_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_account_summary("public-value", "private-value")

    assert isinstance(use_case, GetAccountSummary)
    account_service = use_case._account_service
    assert isinstance(account_service, AccountService)
    adapter = account_service._client
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_account_summary_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def account_summary(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_account_summary("public-value", "private-value")


def test_account_summary_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_account_summary("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_broker_report_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_broker_report(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_broker_report("public-value", "private-value")

    assert isinstance(use_case, GetBrokerReport)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_corporate_actions_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def corporate_actions(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_corporate_actions("public-value", "private-value")

    assert isinstance(use_case, GetCorporateActions)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_price_alerts_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_price_alerts(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_price_alerts("public-value", "private-value")

    assert isinstance(use_case, GetPriceAlerts)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_requests_history_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_requests_history(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_requests_history("public-value", "private-value")

    assert isinstance(use_case, GetRequestsHistory)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_find_instrument_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_find_instrument("public-value", "private-value")

    assert isinstance(use_case, FindInstrument)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_instrument_search_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def find_symbol(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_find_instrument("public-value", "private-value")


def test_instrument_search_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_find_instrument("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_current_quotes_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_current_quotes("public-value", "private-value")

    assert isinstance(use_case, GetCurrentQuotes)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_current_quotes_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_quotes(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_current_quotes("public-value", "private-value")


def test_current_quotes_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_current_quotes("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_historical_candles_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_historical_candles(
        "public-value",
        "private-value",
    )

    assert isinstance(use_case, GetHistoricalCandles)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_news_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_news("public-value", "private-value")

    assert isinstance(use_case, GetNews)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_market_status_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_market_status("public-value", "private-value")

    assert isinstance(use_case, GetMarketStatus)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_historical_builds_expected_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def get_historical(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_historical("public-value", "private-value")

    assert isinstance(use_case, GetHistorical)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_symbols_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def symbols(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public: str, private: str) -> NetworkGuardSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_symbols("public-value", "private-value")

    assert isinstance(use_case, GetSymbols)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_symbol_builds_graph_without_sdk_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    class NetworkGuardSdkClient:
        def symbol(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    sdk_client = NetworkGuardSdkClient()

    def create_sdk_client(public_key: str, private_key: str) -> NetworkGuardSdkClient:
        calls.append((public_key, private_key))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_symbol("public-value", "private-value")

    assert isinstance(use_case, GetSymbol)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_create_get_most_traded_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_most_traded("public-value", "private-value")

    assert isinstance(use_case, GetMostTraded)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_most_traded_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_most_traded(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_most_traded("public-value", "private-value")


def test_most_traded_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_most_traded("public-value", "private-value")

    assert exc_info.value is original


def test_market_status_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_market_status(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_market_status("public-value", "private-value")


def test_market_status_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_market_status("public-value", "private-value")

    assert exc_info.value is original


def test_news_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_news(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_news("public-value", "private-value")


def test_news_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_news("public-value", "private-value")

    assert exc_info.value is original


def test_historical_candles_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_candles(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_historical_candles("public-value", "private-value")


def test_historical_candles_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_historical_candles("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_placed_orders_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_placed_orders("public-value", "private-value")

    assert isinstance(use_case, GetPlacedOrders)
    account_service = use_case._account_service
    assert isinstance(account_service, AccountService)
    adapter = account_service._client
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_placed_orders_composition_does_not_execute_sdk_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_placed(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

        def user_info(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

        def account_summary(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_placed_orders("public-value", "private-value")


def test_placed_orders_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_placed_orders("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_security_info_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_security_info("public-value", "private-value")

    assert isinstance(use_case, GetSecurityInfo)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_composition_does_not_call_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def security_info(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_security_info("public-value", "private-value")


def test_create_get_trades_history_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_trades_history("public-value", "private-value")

    assert isinstance(use_case, GetTradesHistory)
    account_service = use_case._account_service
    assert isinstance(account_service, AccountService)
    adapter = account_service._client
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_trades_history_composition_does_not_execute_sdk_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_trades_history(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

        def get_placed(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

        def user_info(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

        def account_summary(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    use_case = app.create_get_trades_history("public-value", "private-value")

    assert isinstance(use_case, GetTradesHistory)


def test_trades_history_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_trades_history("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_user_info_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_user_info("public-value", "private-value")

    assert isinstance(use_case, GetUserInfo)
    account_service = use_case._account_service
    assert isinstance(account_service, AccountService)
    adapter = account_service._client
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_user_info_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def user_info(self) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_user_info("public-value", "private-value")


def test_user_info_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_user_info("public-value", "private-value")

    assert exc_info.value is original


def test_each_call_builds_a_separate_object_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app, "Tradernet", lambda public, private: FakeSdkClient())

    first = app.create_get_security_info("public-value", "private-value")
    second = app.create_get_security_info("public-value", "private-value")

    assert first is not second
    assert first._market_service is not second._market_service
    assert first._market_service._adapter is not second._market_service._adapter
    assert (
        first._market_service._adapter._client
        is not second._market_service._adapter._client
    )


def test_private_key_is_absent_from_composed_object_reprs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = "private-secret-value"
    monkeypatch.setattr(app, "Tradernet", lambda public, private: FakeSdkClient())

    use_case = app.create_get_security_info("public-value", private_key)
    market_service = use_case._market_service
    adapter = market_service._adapter

    assert private_key not in repr(use_case)
    assert private_key not in repr(market_service)
    assert private_key not in repr(adapter)


def test_app_module_has_no_environment_cli_or_process_boundary_imports() -> None:
    tree = ast.parse(inspect.getsource(app))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "os" not in imported_modules
    assert "kase_pilot.main" not in imported_modules
    assert "kase_pilot.cli" not in imported_modules
    assert "main" not in imported_names
    assert "run" not in imported_names
