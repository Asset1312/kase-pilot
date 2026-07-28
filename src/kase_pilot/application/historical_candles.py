"""Application use case for retrieving historical broker candles."""

from __future__ import annotations

from kase_pilot.broker import MarketService
from kase_pilot.broker.models import JsonValue


class GetHistoricalCandles:
    """Retrieve historical candles for one broker instrument."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        symbol: str,
    ) -> dict[str, JsonValue]:
        """Execute the historical-candles use case."""
        return self._market_service.get_candles(symbol)
