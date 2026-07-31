"""Application use case for retrieving one broker news item's full detail."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetNewsDetail:
    """Retrieve full detail for one broker news item."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self, news_id: int) -> dict[str, Any]:
        """Execute the news-detail use case."""
        return self._market_service.get_news_detail(news_id)
