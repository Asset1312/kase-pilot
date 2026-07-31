"""Application use case for searching KASE Pilot's local instrument catalog."""

from __future__ import annotations

from typing import Any

from kase_pilot.catalog import LocalInstrumentCatalog


class SearchInstruments:
    """Search instruments in KASE Pilot's local catalog by free-text query."""

    def __init__(self, catalog: LocalInstrumentCatalog) -> None:
        self._catalog = catalog

    def execute(self, query: str) -> list[dict[str, Any]]:
        """Execute the instrument search use case."""
        return self._catalog.find(query)
