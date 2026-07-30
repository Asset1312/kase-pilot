"""Application use case for retrieving symbol lists."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetSymbols:
    """Retrieve raw broker symbol lists."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        """Execute the symbols use case."""
        return self._market_service.get_symbols(exchange)
