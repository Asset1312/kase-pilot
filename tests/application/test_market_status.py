"""Tests for the market-status application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetMarketStatus


class FakeMarketService:
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


def test_execute_delegates_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"markets": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetMarketStatus(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == [("*", None)]
    assert result is response


def test_execute_delegates_explicit_arguments() -> None:
    market = "KASE"
    mode = "demo"
    response = {"result": {"markets": []}}
    market_service = FakeMarketService(response)
    use_case = GetMarketStatus(market_service)  # type: ignore[arg-type]

    result = use_case.execute(market, mode=mode)

    assert market_service.calls == [(market, mode)]
    assert market_service.calls[0][0] is market
    assert market_service.calls[0][1] is mode
    assert result is response


def test_market_service_exception_propagates_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_market_status(
            self,
            market: str = "*",
            *,
            mode: str | None = None,
        ) -> dict[str, Any]:
            raise original

    use_case = GetMarketStatus(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_market_status_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetMarketStatus is GetMarketStatus
