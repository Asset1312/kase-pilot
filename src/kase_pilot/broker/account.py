"""Account service for the kase_pilot.broker package."""

from __future__ import annotations

from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter
from kase_pilot.broker.models import JsonValue


class AccountService:
    """Retrieve account information from the broker API."""

    def __init__(self, client: TradernetSdkAdapter) -> None:
        self._client = client

    def user_info(self) -> dict[str, JsonValue]:
        """Return raw information for the authenticated user."""
        return self._client.user_info()

    def account_summary(self) -> dict[str, JsonValue]:
        """Return a raw summary for the authenticated account."""
        return self._client.account_summary()
