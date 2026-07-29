"""Application use case for retrieving client requests history."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from kase_pilot.broker import MarketService


class GetRequestsHistory:
    """Retrieve raw client requests history."""

    def __init__(self, market_service: MarketService) -> None:
        self._market_service = market_service

    def execute(
        self,
        doc_id: int | None = None,
        exec_id: int | None = None,
        start: date = datetime(2011, 1, 11),  # noqa: DTZ001
        end: date = datetime.now(),  # noqa: B008, DTZ005
        limit: int | None = None,
        offset: int | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """Execute the requests-history use case."""
        return self._market_service.get_requests_history(
            doc_id,
            exec_id,
            start,
            end,
            limit,
            offset,
            status,
        )
