"""Application use case for retrieving a broker account summary."""

from __future__ import annotations

from kase_pilot.broker import AccountService
from kase_pilot.broker.models import JsonValue


class GetAccountSummary:
    """Retrieve a raw summary for the authenticated broker account."""

    def __init__(self, account_service: AccountService) -> None:
        self._account_service = account_service

    def execute(self) -> dict[str, JsonValue]:
        """Execute the account-summary use case."""
        return self._account_service.account_summary()
