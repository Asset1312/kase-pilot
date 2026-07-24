"""Portfolio service skeleton for the kase_pilot.broker package."""

from __future__ import annotations

from kase_pilot.broker.client import BrokerClient


class PortfolioService:
    """Retrieves portfolio data from the broker API.

    Parameters
    ----------
    client:
        A fully constructed BrokerClient instance.
    """

    def __init__(self, client: BrokerClient) -> None:
        self._client = client

    def get_positions(self) -> object:
        """Return open positions.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_balances(self) -> object:
        """Return cash balances.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_summary(self) -> object:
        """Return portfolio summary.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
