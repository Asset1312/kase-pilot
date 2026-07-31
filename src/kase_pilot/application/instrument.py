"""Application use case for looking up one catalog instrument by ticker."""

from __future__ import annotations

from typing import Any

from kase_pilot.catalog import LocalInstrumentCatalog


class GetInstrument:
    """Look up one instrument by ticker in KASE Pilot's local catalog."""

    def __init__(self, catalog: LocalInstrumentCatalog) -> None:
        self._catalog = catalog

    def execute(self, ticker: str) -> dict[str, Any] | None:
        """Execute the instrument lookup use case."""
        return self._catalog.get(ticker)
