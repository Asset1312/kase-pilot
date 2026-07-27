"""Tests for the current-quotes application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetCurrentQuotes


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_quotes(self, symbols: object) -> dict[str, Any]:
        self.calls.append(symbols)
        return self.response


def test_execute_delegates_without_transforming_symbols_or_response() -> None:
    symbols = ["AAPL.US", "MSFT.US", "AAPL.US"]
    response = {
        "quotes": {
            "AAPL.US": {
                "last": "211.16",
                "unknown_field": {"nested": [True, None]},
            }
        }
    }
    market_service = FakeMarketService(response)
    use_case = GetCurrentQuotes(market_service)  # type: ignore[arg-type]

    result = use_case.execute(symbols)

    assert market_service.calls == [symbols]
    assert market_service.calls[0] is symbols
    assert result is response
    assert result["quotes"]["AAPL.US"]["last"] == "211.16"  # type: ignore[index]


def test_market_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_quotes(self, symbols: object) -> dict[str, Any]:
            raise original

    use_case = GetCurrentQuotes(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute(["AAPL.US"])

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_get_current_quotes_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetCurrentQuotes is GetCurrentQuotes
