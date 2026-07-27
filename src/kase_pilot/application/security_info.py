"""Application use case for retrieving broker instrument information."""

from __future__ import annotations

from kase_pilot.broker import MarketService
from kase_pilot.broker.models import JsonValue


class GetSecurityInfo:
    """Retrieve raw information for one broker instrument."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, JsonValue]:
        """Execute the instrument-information use case."""
        return self._market_service.get_security_info(ticker, sup=sup)
