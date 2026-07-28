"""Tests for the trades-history application use case."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from kase_pilot.application import GetTradesHistory


class FakeAccountService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object]] = []

    def get_trades_history(
        self,
        start: object,
        end: object,
    ) -> dict[str, Any]:
        self.calls.append((start, end))
        return self.response


def test_constructor_does_not_call_account_service() -> None:
    account_service = FakeAccountService({})

    GetTradesHistory(account_service)  # type: ignore[arg-type]

    assert account_service.calls == []


def test_execute_delegates_dates_and_preserves_response_identity() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    trades = [{"id": 17, "price": "211.16"}]
    response = {
        "trades": trades,
        "unknown_field": {"nested": [True, None]},
    }
    account_service = FakeAccountService(response)
    use_case = GetTradesHistory(account_service)  # type: ignore[arg-type]

    result = use_case.execute(start, end)

    assert account_service.calls == [(start, end)]
    assert account_service.calls[0][0] is start
    assert account_service.calls[0][1] is end
    assert result is response
    assert result["trades"] is trades
    assert result["unknown_field"] is response["unknown_field"]


def test_account_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("account service failed")

    class FailingAccountService:
        def get_trades_history(
            self,
            start: object,
            end: object,
        ) -> dict[str, Any]:
            raise original

    use_case = GetTradesHistory(FailingAccountService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute(date(2025, 1, 1), date(2025, 2, 1))

    assert exc_info.value is original
    assert capsys.readouterr() == ("", "")


def test_get_trades_history_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetTradesHistory is GetTradesHistory
