"""Tests for the trade-ticks application use case."""

from __future__ import annotations

from typing import Any

from kase_pilot.application import GetTicks


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_trades(self, symbol: object) -> dict[str, Any]:
        self.calls.append(symbol)
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    symbol = "AAPL.US"
    response = {"AAPL.US": {"series": [], "info": {"id": "AAPL.US"}}, "took": 2.759}
    market_service = FakeMarketService(response)
    use_case = GetTicks(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbol)

    assert market_service.calls == [symbol]
    assert result is response


def test_get_ticks_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetTicks is GetTicks
