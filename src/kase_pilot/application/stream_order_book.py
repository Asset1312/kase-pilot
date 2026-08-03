"""Application use case for streaming live order-book updates over WebSocket."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from kase_pilot.broker._tradernet_ws import ReconnectObserver, TradernetWebsocketAdapter


class StreamOrderBook:
    """Stream live order-book (market depth) updates for one instrument."""

    def __init__(self, adapter: TradernetWebsocketAdapter) -> None:
        self._adapter = adapter

    async def execute(
        self,
        symbol: str,
        *,
        reconnect: bool = False,
        observer: ReconnectObserver | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the order-book-streaming use case."""
        async for update in self._adapter.market_depth(
            symbol,
            reconnect=reconnect,
            observer=observer,
        ):
            yield update
