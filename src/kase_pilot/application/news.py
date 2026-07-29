"""Application use case for retrieving broker news."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetNews:
    """Retrieve raw broker news."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        query: str,
        symbol: str | None = None,
        story_id: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Execute the news retrieval use case."""
        return self._market_service.get_news(
            query,
            symbol=symbol,
            story_id=story_id,
            limit=limit,
        )
