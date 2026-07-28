"""Tests for the user-information application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetUserInfo


class FakeAccountService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls = 0

    def user_info(self) -> dict[str, Any]:
        self.calls += 1
        return self.response


def test_execute_delegates_once_without_transforming_response() -> None:
    nested = {"positions": [{"quantity": "12.50", "value": None}]}
    response = {
        "account": nested,
        "unknown_field": [True, {"currency": "KZT"}],
    }
    account_service = FakeAccountService(response)
    use_case = GetUserInfo(account_service)  # type: ignore[arg-type]

    result = use_case.execute()

    assert account_service.calls == 1
    assert result is response
    assert result["account"] is nested
    assert result["unknown_field"] is response["unknown_field"]


def test_account_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("account service failed")

    class FailingAccountService:
        def user_info(self) -> dict[str, Any]:
            raise original

    use_case = GetUserInfo(FailingAccountService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_get_user_info_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetUserInfo is GetUserInfo
