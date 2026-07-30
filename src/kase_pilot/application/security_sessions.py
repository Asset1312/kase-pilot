"""Application use case for listing security sessions."""

from __future__ import annotations

from typing import Any

from kase_pilot.broker import MarketService


class ListSecuritySessions:
    """List raw security sessions through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(self) -> dict[str, Any]:
        """Return security sessions without transforming the broker response."""
        return self._market_service.list_security_sessions()
