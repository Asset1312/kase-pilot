"""Market data service skeleton for the kase_pilot.broker package."""

from __future__ import annotations

from kase_pilot.broker.client import BrokerClient


class MarketService:
    """Retrieves market data from the broker API.

    Parameters
    ----------
    client:
        A fully constructed BrokerClient instance.
    """

    def __init__(self, client: BrokerClient) -> None:
        self._client = client

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
