"""Tests for the price-alerts application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetPriceAlerts


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_price_alerts(self, symbol: object = None) -> dict[str, Any]:
        self.calls.append(symbol)
        return self.response


def test_execute_forwards_none_and_preserves_response_identity() -> None:
    response = {"result": {"alerts": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetPriceAlerts(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == [None]
    assert result is response


def test_execute_forwards_explicit_symbol_unchanged() -> None:
    symbol = " Aapl.US "
    market_service = FakeMarketService({})
    use_case = GetPriceAlerts(market_service)  # type: ignore[arg-type]

    use_case.execute(symbol)

    assert market_service.calls == [symbol]
    assert market_service.calls[0] is symbol


def test_execute_propagates_service_exception_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_price_alerts(
            self,
            symbol: str | None = None,
        ) -> dict[str, Any]:
            raise original

    use_case = GetPriceAlerts(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_price_alerts_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetPriceAlerts is GetPriceAlerts
