"""Tests for the instruments application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetInstruments


class FakeMarketService:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_all(
        self,
        market: object,
        show_expired: object = False,
    ) -> list[dict[str, Any]]:
        self.calls.append((market, show_expired))
        return self.response


@pytest.mark.parametrize("show_expired", [False, True])
def test_execute_delegates_and_preserves_response_identity(
    show_expired: bool,
) -> None:
    market = " KASE "
    response = [{"ticker": "HSBK.KZ"}]
    market_service = FakeMarketService(response)
    use_case = GetInstruments(market_service)  # type: ignore[arg-type]

    result = use_case.execute(market, show_expired)

    assert market_service.calls == [(market, show_expired)]
    assert market_service.calls[0][0] is market
    assert result is response


def test_get_instruments_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetInstruments is GetInstruments
