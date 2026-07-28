"""Application use case for retrieving broker trades history."""

from __future__ import annotations

from datetime import date

from kase_pilot.broker import AccountService
from kase_pilot.broker.models import JsonValue


class GetTradesHistory:
    """Retrieve raw trades history for the authenticated broker account."""

    def __init__(self, account_service: AccountService) -> None:
        self._account_service = account_service

    def execute(
        self,
        start: date,
        end: date,
        symbol: str | None = None,
    ) -> dict[str, JsonValue]:
        """Execute the trades-history use case."""
        return self._account_service.get_trades_history(
            start,
            end,
            symbol=symbol,
        )
