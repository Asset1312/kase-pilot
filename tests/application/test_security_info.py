"""Tests for the instrument-information application use case."""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from kase_pilot.application import GetSecurityInfo, security_info


class FakeMarketService:
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


def test_execute_passes_ticker_and_default_sup_once() -> None:
    market_service = FakeMarketService({})
    use_case = GetSecurityInfo(market_service)  # type: ignore[arg-type]

    use_case.execute(" aapl.us ")

    assert market_service.calls == [(" aapl.us ", True)]


def test_execute_passes_false_sup() -> None:
    market_service = FakeMarketService({})
    use_case = GetSecurityInfo(market_service)  # type: ignore[arg-type]

    use_case.execute("AAPL.US", sup=False)

    assert market_service.calls == [("AAPL.US", False)]


def test_execute_returns_response_unchanged() -> None:
    response = {
        "nt_ticker": "AAPL.US",
        "min_step": "0.01",
        "lot": "1",
        "unknown_field": {"nested": True},
    }
    use_case = GetSecurityInfo(FakeMarketService(response))  # type: ignore[arg-type]

    result = use_case.execute("AAPL.US")

    assert result is response
    assert result["min_step"] == "0.01"
    assert result["lot"] == "1"
    assert "unknown_field" in result
    assert "mrkt" not in result


def test_market_service_exception_propagates_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_security_info(
            self,
            ticker: str,
            *,
            sup: bool = True,
        ) -> dict[str, Any]:
            raise original

    use_case = GetSecurityInfo(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute("AAPL.US")

    assert exc_info.value is original


def test_application_module_has_no_sdk_imports() -> None:
    tree = ast.parse(inspect.getsource(security_info))
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

    assert "tradernet" not in imported_modules
    assert "kase_pilot.broker._tradernet_sdk" not in imported_modules
    assert "TradernetSdkAdapter" not in vars(security_info)


def test_get_security_info_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.__all__ == [
        "CheckMissingFields",
        "ExportSecurities",
        "FindInstrument",
        "GetAccountSummary",
        "GetBrokerReport",
        "GetCorporateActions",
        "GetCurrentQuotes",
        "GetHistorical",
        "GetHistoricalCandles",
        "GetInstrument",
        "GetInstruments",
        "GetMarketStatus",
        "GetMostTraded",
        "GetNews",
        "GetOptions",
        "GetOrderFiles",
        "GetPlacedOrders",
        "GetPriceAlerts",
        "GetProfileFields",
        "GetRequestsHistory",
        "GetSecurityInfo",
        "GetSymbol",
        "GetSymbols",
        "GetTariffs",
        "GetTradesHistory",
        "GetUserData",
        "GetUserInfo",
        "ListSecuritySessions",
        "SearchInstruments",
        "StreamOrderBook",
        "StreamQuotes",
    ]
    assert application.GetSecurityInfo is GetSecurityInfo
