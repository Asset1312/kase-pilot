"""Application use case for retrieving order files."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class GetOrderFiles:
    """Retrieve raw order files through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        order_id: int | None,
        internal_id: int | None,
    ) -> dict[str, Any]:
        """Return order files without transforming the broker response."""
        return self._market_service.get_order_files(order_id, internal_id)
