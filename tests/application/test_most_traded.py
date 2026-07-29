"""Tests for the most-traded application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetMostTraded


class FakeMarketService:
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


def test_execute_delegates_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"items": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetMostTraded(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == [("stocks", "usa", True, 10)]
    assert result is response


def test_execute_delegates_explicit_arguments() -> None:
    instrument_type = "bonds"
    exchange = "europe"
    gainers = False
    limit = 25
    response = {"result": {"items": []}}
    market_service = FakeMarketService(response)
    use_case = GetMostTraded(market_service)  # type: ignore[arg-type]

    result = use_case.execute(
        instrument_type,
        exchange=exchange,
        gainers=gainers,
        limit=limit,
    )

    assert market_service.calls == [(instrument_type, exchange, gainers, limit)]
    assert market_service.calls[0][0] is instrument_type
    assert market_service.calls[0][1] is exchange
    assert market_service.calls[0][2] is gainers
    assert market_service.calls[0][3] is limit
    assert result is response


def test_market_service_exception_propagates_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_most_traded(
            self,
            instrument_type: str = "stocks",
            *,
            exchange: str = "usa",
            gainers: bool = True,
            limit: int = 10,
        ) -> dict[str, Any]:
            raise original

    use_case = GetMostTraded(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_most_traded_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetMostTraded is GetMostTraded
