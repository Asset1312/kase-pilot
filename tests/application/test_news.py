"""Tests for the news application use case."""

from __future__ import annotations

from typing import Any

import pytest

from kase_pilot.application import GetNews


class FakeMarketService:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[object, object, object, object]] = []

    def get_news(
        self,
        query: object,
        *,
        symbol: object = None,
        story_id: object = None,
        limit: object = 30,
    ) -> dict[str, Any]:
        self.calls.append((query, symbol, story_id, limit))
        return self.response


def test_execute_delegates_defaults_and_preserves_response_identity() -> None:
    query = "Казахстан"
    response = {"result": {"items": [{"unknown": {"nested": [True, None]}}]}}
    market_service = FakeMarketService(response)
    use_case = GetNews(market_service)  # type: ignore[arg-type]

    result = use_case.execute(query)

    assert market_service.calls == [(query, None, None, 30)]
    assert market_service.calls[0][0] is query
    assert result is response


def test_execute_delegates_explicit_arguments() -> None:
    query = "ignored"
    symbol = "AAPL.US"
    story_id = "story-17"
    limit = 7
    response = {"result": {"items": []}}
    market_service = FakeMarketService(response)
    use_case = GetNews(market_service)  # type: ignore[arg-type]

    result = use_case.execute(
        query,
        symbol=symbol,
        story_id=story_id,
        limit=limit,
    )

    assert market_service.calls == [(query, symbol, story_id, limit)]
    assert result is response


def test_market_service_exception_propagates_unchanged() -> None:
    original = RuntimeError("market service failed")

    class FailingMarketService:
        def get_news(
            self,
            query: str,
            *,
            symbol: str | None = None,
            story_id: str | None = None,
            limit: int = 30,
        ) -> dict[str, Any]:
            raise original

    use_case = GetNews(FailingMarketService())  # type: ignore[arg-type]

    with pytest.raises(RuntimeError) as exc_info:
        use_case.execute("query")

    assert exc_info.value is original


def test_get_news_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.GetNews is GetNews
