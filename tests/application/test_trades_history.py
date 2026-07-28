"""Tests for the trades-history application use case."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from kase_pilot.application import GetTradesHistory

_UNSET = object()


class FakeAccountService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object, object]] = []

    def get_trades_history(
        self,
        start: object,
        end: object,
        *,
        symbol: object = _UNSET,
        limit: object = _UNSET,
    ) -> dict[str, Any]:
        self.calls.append((start, end, symbol, limit))
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

    assert account_service.calls == [(start, end, None, None)]
    assert account_service.calls[0][0] is start
    assert account_service.calls[0][1] is end
    assert result is response
    assert result["trades"] is trades
    assert result["unknown_field"] is response["unknown_field"]


def test_execute_delegates_symbol_without_normalizing_it() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    response = {"unknown_field": {"nested": [True, None]}}
    account_service = FakeAccountService(response)
    use_case = GetTradesHistory(account_service)  # type: ignore[arg-type]

    result = use_case.execute(start, end, symbol=symbol)

    assert account_service.calls == [(start, end, symbol, None)]
    assert account_service.calls[0][0] is start
    assert account_service.calls[0][1] is end
    assert account_service.calls[0][2] is symbol
    assert result is response
    assert result["unknown_field"] is response["unknown_field"]


@pytest.mark.parametrize("limit", [0, -1, 10**100, True])
def test_execute_delegates_limit_without_validation(limit: int) -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    account_service = FakeAccountService({})
    use_case = GetTradesHistory(account_service)  # type: ignore[arg-type]

    result = use_case.execute(start, end, limit=limit)

    assert account_service.calls == [(start, end, None, limit)]
    assert account_service.calls[0][0] is start
    assert account_service.calls[0][1] is end
    assert account_service.calls[0][3] is limit
    assert result is account_service.response


def test_execute_delegates_symbol_and_limit_together() -> None:
    start = date(2025, 1, 1)
    end = date(2025, 2, 1)
    symbol = "  aApL.Us  "
    limit = 250
    account_service = FakeAccountService({})
    use_case = GetTradesHistory(account_service)  # type: ignore[arg-type]

    use_case.execute(start, end, symbol=symbol, limit=limit)

    assert account_service.calls == [(start, end, symbol, limit)]
    assert account_service.calls[0][0] is start
    assert account_service.calls[0][1] is end
    assert account_service.calls[0][2] is symbol
    assert account_service.calls[0][3] is limit


def test_account_service_exception_propagates_unchanged_without_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    original = RuntimeError("account service failed")

    class FailingAccountService:
        def get_trades_history(
            self,
            start: object,
            end: object,
            *,
            symbol: object = None,
            limit: object = None,
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
