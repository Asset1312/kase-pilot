"""Application use case for retrieving instruments by market."""

from __future__ import annotations

from typing import Any

from kase_pilot.catalog import LocalInstrumentCatalog


class GetInstruments:
    """Retrieve instruments for one market from KASE Pilot's local catalog."""

    def __init__(self, catalog: LocalInstrumentCatalog) -> None:
        self._catalog = catalog

    def execute(
        self,
        market: str,
        show_expired: bool = False,
    ) -> list[dict[str, Any]]:
        """Execute the instruments use case."""
        return self._catalog.get_all(market, show_expired)
