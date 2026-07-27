"""Tests for the internal Tradernet SDK adapter."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class FakeSdkClient:
    def __init__(self, response: Any) -> None:
        self.response = response
        self.calls: list[tuple[str, bool]] = []

    def security_info(self, ticker: str, *, sup: bool = True) -> Any:
        self.calls.append((ticker, sup))
        return self.response


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


def test_broker_public_exports_are_unchanged() -> None:
    assert broker.__all__ == [
        "BrokerClient",
        "MarketService",
        "OrdersService",
        "PortfolioService",
        "ReportsService",
    ]
    assert "TradernetSdkAdapter" not in broker.__all__
    assert not hasattr(broker, "TradernetSdkAdapter")
