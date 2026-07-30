"""Application use case for checking missing profile fields."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class CheckMissingFields:
    """Check raw missing profile fields through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        step: int,
        office: str,
    ) -> dict[str, Any]:
        """Return missing fields without transforming the broker response."""
        return self._market_service.check_missing_fields(step, office)
