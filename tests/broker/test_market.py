"""Tests for the market-data broker service."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker.market import MarketService


class FakeSecurityInfoDependency:
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


def test_get_security_info_passes_ticker_and_default_sup_once() -> None:
    dependency = FakeSecurityInfoDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_security_info(" aapl.us ")

    assert dependency.calls == [(" aapl.us ", True)]


def test_get_security_info_passes_false_sup() -> None:
    dependency = FakeSecurityInfoDependency({})
    service = MarketService(dependency)  # type: ignore[arg-type]

    service.get_security_info("AAPL.US", sup=False)

    assert dependency.calls == [("AAPL.US", False)]


def test_get_security_info_returns_response_unchanged() -> None:
    response = {
        "nt_ticker": "AAPL.US",
        "min_step": "0.01",
        "lot": "1",
        "unknown_field": {"nested": True},
    }
    dependency = FakeSecurityInfoDependency(response)
    service = MarketService(dependency)  # type: ignore[arg-type]

    result = service.get_security_info("AAPL.US")

    assert result is response
    assert result["min_step"] == "0.01"
    assert result["lot"] == "1"
    assert "unknown_field" in result
    assert "mrkt" not in result


def test_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def get_security_info(
            self,
            ticker: str,
            *,
            sup: bool = True,
        ) -> dict[str, Any]:
            raise original

    service = MarketService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.get_security_info("AAPL.US")

    assert exc_info.value is original


def test_market_service_is_public_but_sdk_adapter_is_not() -> None:
    assert broker.MarketService is MarketService
    assert "MarketService" in broker.__all__
    assert "TradernetSdkAdapter" not in broker.__all__
    assert not hasattr(broker, "TradernetSdkAdapter")
