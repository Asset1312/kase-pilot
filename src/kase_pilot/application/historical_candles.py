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
        timeframe: int | None = None,
    ) -> dict[str, JsonValue]:
        """Execute the historical-candles use case."""
        if timeframe is not None:
            return self._market_service.get_candles(
                symbol,
                timeframe=timeframe,
            )
        return self._market_service.get_candles(symbol)
