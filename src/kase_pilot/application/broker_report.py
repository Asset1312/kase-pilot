"""Application use case for retrieving a broker report."""

from __future__ import annotations

from datetime import date, time
from typing import Any

from kase_pilot.broker import MarketService


class GetBrokerReport:
    """Retrieve a raw broker report."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        start: str | date = date(1970, 1, 1),
        end: str | date = date.today(),  # noqa: B008, DTZ011
        period: time = time(23, 59, 59),
    ) -> dict[str, Any]:
        """Execute the broker-report use case."""
        return self._market_service.get_broker_report(
            start=start,
            end=end,
            period=period,
        )
