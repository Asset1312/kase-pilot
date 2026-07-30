"""Application use case for retrieving instruments by market."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetInstruments:
    """Retrieve raw broker instruments for one market."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        market: str,
        show_expired: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute the instruments use case."""
        return self._market_service.get_all(market, show_expired)
