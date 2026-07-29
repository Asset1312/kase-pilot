"""Application use case for retrieving most-traded market data."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetMostTraded:
    """Retrieve raw most-traded market data."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        instrument_type: str = "stocks",
        exchange: str = "usa",
        gainers: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Execute the most-traded use case."""
        return self._market_service.get_most_traded(
            instrument_type,
            exchange=exchange,
            gainers=gainers,
            limit=limit,
        )
