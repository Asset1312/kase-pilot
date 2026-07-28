"""Application use case for retrieving broker user information."""

from __future__ import annotations

from kase_pilot.broker import AccountService
from kase_pilot.broker.models import JsonValue


class GetUserInfo:
    """Retrieve raw information for the authenticated broker user."""

    def __init__(self, account_service: AccountService) -> None:
        self._account_service = account_service

    def execute(self) -> dict[str, JsonValue]:
        """Execute the user-information use case."""
        return self._account_service.user_info()
