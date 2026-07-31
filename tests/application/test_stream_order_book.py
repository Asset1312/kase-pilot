"""Tests for the order-book-streaming application use case."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from kase_pilot.application import StreamOrderBook


class FakeAdapter:
    def __init__(self, messages: list[dict[str, Any]]) -> None:
        self._messages = messages
        self.calls: list[str] = []

    async def market_depth(self, symbol: str) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(symbol)
        for message in self._messages:
            yield message


def _collect(use_case: StreamOrderBook, symbol: str) -> list[Any]:
    async def run() -> list[Any]:
        return [update async for update in use_case.execute(symbol)]

    return asyncio.run(run())


def test_execute_delegates_and_preserves_message_identity() -> None:
    messages = [{"c": "HSBK.KZ"}, {"c": "HSBK.KZ"}]
    adapter = FakeAdapter(messages)
    use_case = StreamOrderBook(adapter)  # type: ignore[arg-type]

    result = _collect(use_case, "HSBK.KZ")

    assert result == messages
    assert result[0] is messages[0]


def test_execute_forwards_symbol_unchanged() -> None:
    adapter = FakeAdapter([])
    use_case = StreamOrderBook(adapter)  # type: ignore[arg-type]

    _collect(use_case, "HSBK.KZ")

    assert adapter.calls == ["HSBK.KZ"]


def test_stream_order_book_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.StreamOrderBook is StreamOrderBook
