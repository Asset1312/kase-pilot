"""Application use case for streaming live quotes over WebSocket."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

from kase_pilot.broker._tradernet_ws import ReconnectObserver, TradernetWebsocketAdapter


class StreamQuotes:
    """Stream live quote updates for one or more instruments."""

    def __init__(self, adapter: TradernetWebsocketAdapter) -> None:
        self._adapter = adapter

    async def execute(
        self,
        symbols: Sequence[str],
        *,
        reconnect: bool = False,
        observer: ReconnectObserver | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the quote-streaming use case."""
        async for quote in self._adapter.quotes(
            symbols,
            reconnect=reconnect,
            observer=observer,
        ):
            yield quote
