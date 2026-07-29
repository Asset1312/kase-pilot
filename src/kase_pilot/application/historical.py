"""Application use case for retrieving historical orders."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kase_pilot.broker import MarketService


class GetHistorical:
    """Retrieve raw historical orders."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        start: datetime = datetime(2011, 1, 11),  # noqa: DTZ001
        end: datetime = datetime.now(),  # noqa: B008, DTZ005
    ) -> dict[str, Any]:
        """Execute the historical-orders use case."""
        return self._market_service.get_historical(start, end)
