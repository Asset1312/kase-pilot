"""Tests for the historical-orders application use case."""

from __future__ import annotations

from datetime import UTC, datetime
from inspect import signature
from typing import Any

import pytest

from kase_pilot.application import GetHistorical


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_historical(self, start: object, end: object) -> dict[str, Any]:
        self.calls.append((start, end))
        return self.response


def test_execute_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"orders": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetHistorical(market_service)  # type: ignore[arg-type]
    parameters = signature(GetHistorical.execute).parameters

    result = use_case.execute()

    assert market_service.calls == [
        (parameters["start"].default, parameters["end"].default)
    ]
    assert result is response


def test_execute_forwards_explicit_datetimes_unchanged() -> None:
    start = datetime(2024, 1, 1, 9, 30, tzinfo=UTC)
    end = datetime(2024, 2, 1, 16, 0, tzinfo=UTC)
    market_service = FakeMarketService({})
    use_case = GetHistorical(market_service)  # type: ignore[arg-type]

    use_case.execute(start, end)

    assert market_service.calls == [(start, end)]
    assert market_service.calls[0][0] is start
    assert market_service.calls[0][1] is end


def test_execute_propagates_service_exception_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_historical(self, start: datetime, end: datetime) -> dict[str, Any]:
            raise original

    use_case = GetHistorical(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_historical_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetHistorical is GetHistorical
