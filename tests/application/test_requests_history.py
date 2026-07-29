"""Tests for the requests-history application use case."""

from __future__ import annotations

from datetime import date
from inspect import signature
from typing import Any

import pytest

from kase_pilot.application import GetRequestsHistory


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[
            tuple[object, object, object, object, object, object, object]
        ] = []

    def get_requests_history(
        self,
        doc_id: object = None,
        exec_id: object = None,
        start: object = None,
        end: object = None,
        limit: object = None,
        offset: object = None,
        status: object = None,
    ) -> dict[str, Any]:
        self.calls.append((doc_id, exec_id, start, end, limit, offset, status))
        return self.response


def test_execute_forwards_defaults_and_preserves_response_identity() -> None:
    response = {"result": {"requests": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetRequestsHistory(market_service)  # type: ignore[arg-type]
    parameters = signature(GetRequestsHistory.execute).parameters

    result = use_case.execute()

    assert market_service.calls == [
        (
            None,
            None,
            parameters["start"].default,
            parameters["end"].default,
            None,
            None,
            None,
        )
    ]
    assert result is response


def test_execute_forwards_all_explicit_arguments_unchanged() -> None:
    doc_id = 17
    exec_id = 23
    start = date(2026, 1, 1)
    end = date(2026, 2, 1)
    limit = 50
    offset = 10
    status = 3
    market_service = FakeMarketService({})
    use_case = GetRequestsHistory(market_service)  # type: ignore[arg-type]

    use_case.execute(
        doc_id,
        exec_id,
        start,
        end,
        limit,
        offset,
        status,
    )

    assert market_service.calls == [
        (doc_id, exec_id, start, end, limit, offset, status)
    ]
    assert market_service.calls[0][2] is start
    assert market_service.calls[0][3] is end


def test_execute_propagates_service_exception_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_requests_history(
            self,
            doc_id: int | None,
            exec_id: int | None,
            start: date,
            end: date,
            limit: int | None,
            offset: int | None,
            status: int | None,
        ) -> dict[str, Any]:
            raise original

    use_case = GetRequestsHistory(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute()

    assert exc_info.value is original


def test_get_requests_history_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetRequestsHistory is GetRequestsHistory
