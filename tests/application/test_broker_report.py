"""Tests for the broker-report application use case."""

from __future__ import annotations

from datetime import date, time
from inspect import signature
from typing import Any

import pytest

from kase_pilot.application import GetBrokerReport


class FakeMarketService:
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


def test_execute_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"trades": [{"unknown": {"nested": [True, None]}}]}
    market_service = FakeMarketService(response)
    use_case = GetBrokerReport(market_service)  # type: ignore[arg-type]
    parameters = signature(GetBrokerReport.execute).parameters

    result = use_case.execute()

    assert market_service.calls == [
        (
            parameters["start"].default,
            parameters["end"].default,
            parameters["period"].default,
        )
    ]
    assert result is response


def test_execute_forwards_explicit_arguments_unchanged() -> None:
    start = "2026-01-01"
    end = date(2026, 1, 31)
    period = time(18, 30, 15)
    market_service = FakeMarketService({})
    use_case = GetBrokerReport(market_service)  # type: ignore[arg-type]

    use_case.execute(start=start, end=end, period=period)

    assert market_service.calls == [(start, end, period)]
    assert market_service.calls[0][0] is start
    assert market_service.calls[0][1] is end
    assert market_service.calls[0][2] is period


def test_execute_propagates_service_exception_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_broker_report(
            self,
            *,
            start: str | date,
            end: str | date,
            period: time,
        ) -> dict[str, Any]:
            raise original

    use_case = GetBrokerReport(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_broker_report_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetBrokerReport is GetBrokerReport
