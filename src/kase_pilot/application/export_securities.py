"""Application use case for exporting securities."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from kase_pilot.broker import MarketService


class ExportSecurities:
    """Export raw securities data through the broker service."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        symbols: Sequence[str],
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Return an unmodified securities export."""
        return self._market_service.export_securities(symbols, fields)
