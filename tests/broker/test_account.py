"""Tests for the account broker service."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot import broker
from kase_pilot.broker.account import AccountService


class FakeAccountDependency:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def user_info(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


def test_user_info_delegates_once_without_transforming_response() -> None:
    nested = {"positions": [{"quantity": "12.50", "value": None}]}
    response = {"account": nested, "unknown_field": [True]}
    dependency = FakeAccountDependency(response)
    service = AccountService(dependency)  # type: ignore[arg-type]

    result = service.user_info()

    assert dependency.calls == 1
    assert result is response
    assert result["account"] is nested
    assert result["unknown_field"] is response["unknown_field"]


def test_user_info_dependency_exception_propagates_unchanged() -> None:
    original = RuntimeError("dependency failed")

    class FailingDependency:
        def user_info(self) -> dict[str, Any]:
            raise original

    service = AccountService(FailingDependency())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        service.user_info()

    assert exc_info.value is original


def test_account_service_is_public_but_sdk_adapter_is_not() -> None:
    assert broker.AccountService is AccountService
    assert "AccountService" in broker.__all__
    assert "TradernetSdkAdapter" not in broker.__all__
    assert not hasattr(broker, "TradernetSdkAdapter")
