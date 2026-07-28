"""Tests for the placed-orders application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetPlacedOrders


class FakeAccountService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[bool] = []

    def get_placed(self, *, active: bool = True) -> dict[str, Any]:
        self.calls.append(active)
        return self.response


def test_execute_uses_default_active_without_transforming_response() -> None:
    orders = [{"id": 17, "price": "211.16"}]
    response = {
        "orders": orders,
        "unknown_field": {"nested": [True, None]},
    }
    account_service = FakeAccountService(response)
    use_case = GetPlacedOrders(account_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert account_service.calls == [True]
    assert result is response
    assert result["orders"] is orders
    assert result["unknown_field"] is response["unknown_field"]


def test_execute_passes_false_active() -> None:
    account_service = FakeAccountService({})
    use_case = GetPlacedOrders(account_service)  # type: ignore[arg-type]

    use_case.execute(active=False)

    assert account_service.calls == [False]


def test_account_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("account service failed")

    class FailingAccountService:
        def get_placed(self, *, active: bool = True) -> dict[str, Any]:
            raise original

    use_case = GetPlacedOrders(FailingAccountService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_get_placed_orders_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetPlacedOrders is GetPlacedOrders
