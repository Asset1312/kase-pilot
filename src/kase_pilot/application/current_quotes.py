"""Application use case for retrieving current broker quotes."""

from __future__ import annotations

from collections.abc import Sequence

from kase_pilot.broker import MarketService
from kase_pilot.broker.models import JsonValue


class GetCurrentQuotes:
    """Retrieve current quotes for broker instruments."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        symbols: Sequence[str],
    ) -> dict[str, JsonValue]:
        """Execute the current-quotes use case."""
        return self._market_service.get_quotes(symbols)
