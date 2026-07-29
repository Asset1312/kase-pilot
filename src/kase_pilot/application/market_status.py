"""Application use case for retrieving market status."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetMarketStatus:
    """Retrieve raw market status information."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        market: str = "*",
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Execute the market-status use case."""
        return self._market_service.get_market_status(market, mode=mode)
