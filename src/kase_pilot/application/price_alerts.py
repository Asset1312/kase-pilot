"""Application use case for retrieving price alerts."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetPriceAlerts:
    """Retrieve raw price alerts."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Execute the price-alerts use case."""
        return self._market_service.get_price_alerts(symbol)
