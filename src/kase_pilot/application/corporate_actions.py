"""Application use case for retrieving planned corporate actions."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetCorporateActions:
    """Retrieve raw planned corporate actions."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        reception: int = 35,
    ) -> list[dict[str, Any]]:
        """Execute the corporate-actions use case."""
        return self._market_service.corporate_actions(reception)
