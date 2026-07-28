"""Application use case for retrieving placed broker orders."""

from __future__ import annotations

from kase_pilot.broker import AccountService
from kase_pilot.broker.models import JsonValue


class GetPlacedOrders:
    """Retrieve raw placed orders for the authenticated broker account."""

    def __init__(self, account_service: AccountService) -> None:
        self._account_service = account_service

    def execute(
        self,
        active: bool = True,
    ) -> dict[str, JsonValue]:
        """Execute the placed-orders use case."""
        return self._account_service.get_placed(active=active)
