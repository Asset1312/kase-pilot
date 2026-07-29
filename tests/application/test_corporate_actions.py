"""Tests for the corporate-actions application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetCorporateActions


class FakeMarketService:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[object] = []

    def corporate_actions(self, reception: object = 35) -> list[dict[str, Any]]:
        self.calls.append(reception)
        return self.response


def test_execute_forwards_default_and_preserves_list_identity() -> None:
    response = [{"id": "action-1", "unknown": {"nested": [True, None]}}]
    market_service = FakeMarketService(response)
    use_case = GetCorporateActions(market_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert market_service.calls == [35]
    assert result is response


def test_execute_forwards_explicit_reception_unchanged() -> None:
    reception = 17
    market_service = FakeMarketService([])
    use_case = GetCorporateActions(market_service)  # type: ignore[arg-type]

    use_case.execute(reception)

    assert market_service.calls == [reception]
    assert market_service.calls[0] is reception


def test_execute_propagates_service_exception_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def corporate_actions(
            self,
            reception: int = 35,
        ) -> list[dict[str, Any]]:
            raise original

    use_case = GetCorporateActions(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_corporate_actions_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetCorporateActions is GetCorporateActions
