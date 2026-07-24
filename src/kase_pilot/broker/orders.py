"""Orders and trades service skeleton for the kase_pilot.broker package."""

from __future__ import annotations

from kase_pilot.broker.client import BrokerClient


class OrdersService:
    """Retrieves order and trade data from the broker API (read-only).

    Parameters
    ----------
    client:
        A fully constructed BrokerClient instance.
    """

    def __init__(self, client: BrokerClient) -> None:
        self._client = client

    def get_current_orders(self) -> object:
        """Return current open orders.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_order_history(self) -> object:
        """Return historical orders.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_trade_history(self) -> object:
        """Return trade history.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
