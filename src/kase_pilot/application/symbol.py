"""Application use case for retrieving symbol information."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetSymbol:
    """Retrieve raw broker symbol information."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        symbol: str,
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Execute the symbol use case."""
        return self._market_service.get_symbol(symbol, lang)
