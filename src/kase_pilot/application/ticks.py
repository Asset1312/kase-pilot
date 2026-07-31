"""Application use case for retrieving raw broker trade ticks."""

from __future__ import annotations

from kase_pilot.broker import MarketService
from kase_pilot.broker.models import JsonValue


class GetTicks:
    """Retrieve raw trade ticks for one broker instrument."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self, symbol: str) -> dict[str, JsonValue]:
        """Execute the trade-ticks use case."""
        return self._market_service.get_trades(symbol)
