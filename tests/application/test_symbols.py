"""Tests for the symbols application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetSymbols


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[object] = []

    def get_symbols(self, exchange: object = None) -> dict[str, Any]:
        self.calls.append(exchange)
        return self.response


@pytest.mark.parametrize("exchange", [None, " KASE "])
def test_execute_delegates_and_preserves_response_identity(
    exchange: str | None,
) -> None:
    response = {"result": {"symbols": [{"ticker": "HSBK.KZ"}]}}
    market_service = FakeMarketService(response)
    use_case = GetSymbols(market_service)  # type: ignore[arg-type]

    result = use_case.execute(exchange)

    assert market_service.calls == [exchange]
    assert result is response


def test_get_symbols_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetSymbols is GetSymbols
