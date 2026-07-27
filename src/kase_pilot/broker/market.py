"""Market data service for the kase_pilot.broker package."""

from __future__ import annotations

from collections.abc import Sequence

from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter
from kase_pilot.broker.models import JsonValue


class MarketService:
    """Retrieves market data from the broker API.

    Parameters
    ----------
    adapter:
        A fully constructed internal Tradernet SDK adapter.
    """

    def __init__(self, adapter: TradernetSdkAdapter) -> None:
        self._adapter = adapter

    def get_security_info(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, JsonValue]:
        """Return raw information for a broker instrument."""
        return self._adapter.get_security_info(ticker, sup=sup)

    def get_quotes(
        self,
        symbols: Sequence[str],
    ) -> dict[str, JsonValue]:
        """Return current quotes for broker instruments."""
        return self._adapter.get_quotes(symbols)

    def get_current_quotes(self) -> object:
        """Return current quotes.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_historical_quotes(self) -> object:
        """Return historical quotes.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
