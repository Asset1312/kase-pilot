"""Application use case for retrieving profile fields."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetProfileFields:
    """Retrieve raw profile fields through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self, reception: int) -> dict[str, Any]:
        """Return profile fields without transforming the broker response."""
        return self._market_service.get_profile_fields(reception)
