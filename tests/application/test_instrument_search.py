"""Tests for the instrument-search application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import FindInstrument


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def find_symbol(self, query: object) -> dict[str, Any]:
        self.calls.append(query)
        return self.response


def test_execute_delegates_without_transforming_query_or_response() -> None:
    query = "  aPpLe Inc  "
    response = {
        "items": [
            {
                "ticker": "AAPL.US",
                "price": "211.16",
                "unknown_field": {"nested": [True, None]},
            }
        ]
    }
    market_service = FakeMarketService(response)
    use_case = FindInstrument(market_service)  # type: ignore[arg-type]

    result = use_case.execute(query)

    assert market_service.calls == [query]
    assert market_service.calls[0] is query
    assert result is response
    assert result["items"][0]["price"] == "211.16"  # type: ignore[index]


def test_market_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def find_symbol(self, query: object) -> dict[str, Any]:
            raise original

    use_case = FindInstrument(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute("Apple")

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_find_instrument_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.FindInstrument is FindInstrument
