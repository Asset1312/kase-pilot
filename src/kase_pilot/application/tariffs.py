"""Application use case for retrieving tariffs."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetTariffs:
    """Retrieve raw tariffs through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self) -> dict[str, Any]:
        """Return tariffs without transforming the broker response."""
        return self._market_service.get_tariffs()
