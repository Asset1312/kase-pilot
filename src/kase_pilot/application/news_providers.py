"""Application use case for listing available broker news providers."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetNewsProviders:
    """Retrieve available broker news providers for a language."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self, lang: str | None = None) -> dict[str, Any]:
        """Execute the news-providers use case."""
        return self._market_service.get_news_providers(lang)
