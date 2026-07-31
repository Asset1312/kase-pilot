"""Application use case for retrieving symbol lists."""

from __future__ import annotations

from typing import Any

from kase_pilot.catalog import LocalInstrumentCatalog


class GetSymbols:
    """Retrieve symbol lists from KASE Pilot's local instrument catalog."""

    def __init__(self, catalog: LocalInstrumentCatalog) -> None:
        self._catalog = catalog

    def execute(
        self,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        """Execute the symbols use case."""
        return self._catalog.get_symbols(exchange)
