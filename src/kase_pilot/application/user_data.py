"""Application use case for retrieving user data."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetUserData:
    """Retrieve raw user data through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self) -> dict[str, Any]:
        """Return user data without transforming the broker response."""
        return self._market_service.get_user_data()
