"""Reports service skeleton for the kase_pilot.broker package."""

from __future__ import annotations

from kase_pilot.broker.client import BrokerClient


class ReportsService:
    """Retrieves broker reports from the broker API, if available.

    Availability and format are not yet confirmed.
    See docs/API_NOTES.md §15.

    Parameters
    ----------
    client:
        A fully constructed BrokerClient instance.
    """

    def __init__(self, client: BrokerClient) -> None:
        self._client = client

    def get_reports(self) -> object:
        """Return available broker reports.

        Not implemented.  Report availability, endpoint, and response
        format are deferred until confirmed from official documentation.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
