"""Application use case for listing broker news with pagination."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class ListNews:
    """Retrieve a page of broker news, optionally filtered."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        ticker: str | None = None,
        provider: str | None = None,
        lang: str | None = None,
        take: int = 20,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Execute the news-list use case."""
        return self._market_service.list_news(ticker, provider, lang, take, skip)
