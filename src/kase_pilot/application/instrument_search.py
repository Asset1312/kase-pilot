"""Application use case for finding broker instruments."""

from __future__ import annotations

from kase_pilot.broker import MarketService
from kase_pilot.broker.models import JsonValue


class FindInstrument:
    """Find broker instruments matching a query."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        query: str,
    ) -> dict[str, JsonValue]:
        """Execute the instrument-search use case."""
        return self._market_service.find_symbol(query)
