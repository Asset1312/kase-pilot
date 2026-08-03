"""Tests for the quote-streaming application use case."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any

from kase_pilot.application import StreamQuotes


class FakeAdapter:
    def __init__(self, messages: Sequence[dict[str, Any]]) -> None:
        self._messages = messages
        self.calls: list[Sequence[str]] = []

    async def quotes(
        self,
        symbols: Sequence[str],
        **kwargs: object,
    ) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(symbols)
        for message in self._messages:
            yield message


def _collect(use_case: StreamQuotes, symbols: Sequence[str]) -> list[Any]:
    async def run() -> list[Any]:
        return [quote async for quote in use_case.execute(symbols)]

    return asyncio.run(run())


def test_execute_delegates_and_preserves_message_identity() -> None:
    messages = [{"c": "HSBK.KZ"}, {"c": "HSBK.KZ"}]
    adapter = FakeAdapter(messages)
    use_case = StreamQuotes(adapter)  # type: ignore[arg-type]

    result = _collect(use_case, ["HSBK.KZ"])

    assert result == messages
    assert result[0] is messages[0]


def test_execute_forwards_symbols_unchanged() -> None:
    symbols = ["HSBK.KZ", "KSPI.KZ"]
    adapter = FakeAdapter([])
    use_case = StreamQuotes(adapter)  # type: ignore[arg-type]

    _collect(use_case, symbols)

    assert adapter.calls == [symbols]
    assert adapter.calls[0] is symbols


def test_stream_quotes_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.StreamQuotes is StreamQuotes
