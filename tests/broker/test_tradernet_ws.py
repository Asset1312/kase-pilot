"""Tests for the internal Tradernet WebSocket adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, Self

import pytest

import kase_pilot.broker._tradernet_ws as tradernet_ws
from kase_pilot.broker._tradernet_ws import TradernetWebsocketAdapter
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


async def _no_sleep(delay: float) -> None:
    """Skip retry backoff so reconnection tests stay fast."""
    return


class FakeWebsocket:
    """Stands in for tradernet.TradernetWebsocket in tests."""

    def __init__(
        self,
        client: object,
        *,
        messages: Sequence[dict[str, Any]] = (),
        connect_error: Exception | None = None,
        iteration_error: Exception | None = None,
    ) -> None:
        self.client = client
        self._messages = messages
        self._connect_error = connect_error
        self._iteration_error = iteration_error
        self.quotes_calls: list[Sequence[str]] = []
        self.market_depth_calls: list[str] = []

    async def __aenter__(self) -> Self:
        if self._connect_error is not None:
            raise self._connect_error
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def quotes(
        self,
        symbols: Sequence[str],
    ) -> AsyncIterator[dict[str, Any]]:
        self.quotes_calls.append(symbols)
        for message in self._messages:
            yield message
        if self._iteration_error is not None:
            raise self._iteration_error

    async def market_depth(self, symbol: str) -> AsyncIterator[dict[str, Any]]:
        self.market_depth_calls.append(symbol)
        for message in self._messages:
            yield message
        if self._iteration_error is not None:
            raise self._iteration_error


def _install_fake_websocket(
    monkeypatch: pytest.MonkeyPatch,
    fake: FakeWebsocket,
) -> None:
    monkeypatch.setattr(
        tradernet_ws,
        "TradernetWebsocket",
        lambda client: fake,
    )


def _collect(adapter: TradernetWebsocketAdapter, symbols: Sequence[str]) -> list[Any]:
    async def run() -> list[Any]:
        return [quote async for quote in adapter.quotes(symbols)]

    return asyncio.run(run())


def _collect_depth(adapter: TradernetWebsocketAdapter, symbol: str) -> list[Any]:
    async def run() -> list[Any]:
        return [update async for update in adapter.market_depth(symbol)]

    return asyncio.run(run())


def test_quotes_yields_messages_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [{"c": "HSBK.KZ", "ltp": 100.0}, {"c": "HSBK.KZ", "ltp": 100.5}]
    fake = FakeWebsocket(object(), messages=messages)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect(adapter, ["HSBK.KZ"])

    assert result == messages
    assert fake.quotes_calls == [["HSBK.KZ"]]


def test_quotes_forwards_symbols_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    symbols = ["HSBK.KZ", "KSPI.KZ"]
    fake = FakeWebsocket(object())
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    _collect(adapter, symbols)

    assert fake.quotes_calls == [symbols]
    assert fake.quotes_calls[0] is symbols


def test_quotes_rejects_non_mapping_message(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeWebsocket(object(), messages=[["not", "a", "mapping"]])  # type: ignore[list-item]
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping quote message"):
        _collect(adapter, ["HSBK.KZ"])


def test_quotes_wraps_connection_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    original = RuntimeError("connection refused")
    fake = FakeWebsocket(object(), connect_error=original)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        _collect(adapter, ["HSBK.KZ"])

    assert exc_info.value.__cause__ is original


def test_quotes_wraps_iteration_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    original = RuntimeError("stream closed")
    fake = FakeWebsocket(
        object(),
        messages=[{"c": "HSBK.KZ"}],
        iteration_error=original,
    )
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        _collect(adapter, ["HSBK.KZ"])

    assert exc_info.value.__cause__ is original


def test_market_depth_yields_messages_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"c": "HSBK.KZ", "bbp": 383.5}, {"c": "HSBK.KZ", "bbp": 383.6}]
    fake = FakeWebsocket(object(), messages=messages)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect_depth(adapter, "HSBK.KZ")

    assert result == messages
    assert fake.market_depth_calls == ["HSBK.KZ"]


def test_market_depth_forwards_symbol_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeWebsocket(object())
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    _collect_depth(adapter, "HSBK.KZ")

    assert fake.market_depth_calls == ["HSBK.KZ"]


def test_market_depth_rejects_non_mapping_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeWebsocket(object(), messages=[["not", "a", "mapping"]])  # type: ignore[list-item]
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="non-mapping order-book message"):
        _collect_depth(adapter, "HSBK.KZ")


def test_market_depth_wraps_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("connection refused")
    fake = FakeWebsocket(object(), connect_error=original)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        _collect_depth(adapter, "HSBK.KZ")

    assert exc_info.value.__cause__ is original


def test_market_depth_wraps_iteration_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("stream closed")
    fake = FakeWebsocket(
        object(),
        messages=[{"c": "HSBK.KZ"}],
        iteration_error=original,
    )
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError) as exc_info:
        _collect_depth(adapter, "HSBK.KZ")

    assert exc_info.value.__cause__ is original


class FlakyWebsocket:
    """Fails a set number of times, then streams normally."""

    def __init__(self, failures: int, messages: Sequence[dict[str, Any]]) -> None:
        self._remaining_failures = failures
        self._messages = messages
        self.connection_attempts = 0

    async def __aenter__(self) -> Self:
        self.connection_attempts += 1
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def quotes(
        self,
        symbols: Sequence[str],
    ) -> AsyncIterator[dict[str, Any]]:
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("connection dropped")
            yield  # pragma: no cover - unreachable, marks this a generator
        for message in self._messages:
            yield message


def _collect_reconnecting(
    adapter: TradernetWebsocketAdapter,
    symbols: Sequence[str],
    observer: Any = None,
    *,
    count: int = 1,
) -> list[Any]:
    async def run() -> list[Any]:
        results: list[Any] = []
        async for quote in adapter.quotes(
            symbols, reconnect=True, observer=observer
        ):
            results.append(quote)
            if len(results) >= count:
                break
        return results

    return asyncio.run(run())


def test_reconnect_retries_until_the_stream_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"c": "HSBK.KZ", "ltp": 1}]
    fake = FlakyWebsocket(failures=2, messages=messages)
    _install_fake_websocket(monkeypatch, fake)
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    assert _collect_reconnecting(adapter, ["HSBK.KZ"]) == messages
    assert fake.connection_attempts == 3


def test_reconnect_reports_each_failure_and_the_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, int, float]] = []
    fake = FlakyWebsocket(failures=2, messages=[{"c": "HSBK.KZ"}])
    _install_fake_websocket(monkeypatch, fake)
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    _collect_reconnecting(
        adapter,
        ["HSBK.KZ"],
        lambda event, attempt, delay: events.append((event, attempt, delay)),
    )

    assert [event for event, _, _ in events] == ["failed", "failed", "resumed"]
    assert [attempt for _, attempt, _ in events] == [1, 2, 2]


def test_reconnect_backs_off_exponentially(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    delays: list[float] = []
    fake = FlakyWebsocket(failures=3, messages=[{"c": "HSBK.KZ"}])
    _install_fake_websocket(monkeypatch, fake)

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", record_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect_reconnecting(adapter, ["HSBK.KZ"])

    assert result == [{"c": "HSBK.KZ"}]
    assert delays == [1.0, 2.0, 4.0]


def test_reconnect_does_not_retry_validation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed message is not transient; retrying would hide it."""
    fake = FakeWebsocket(object(), messages=[["not", "a", "mapping"]])  # type: ignore[list-item]
    _install_fake_websocket(monkeypatch, fake)
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        _collect_reconnecting(adapter, ["HSBK.KZ"])


def test_without_reconnect_a_failure_still_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FlakyWebsocket(failures=1, messages=[{"c": "HSBK.KZ"}])
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    with pytest.raises(ApiRequestError):
        _collect(adapter, ["HSBK.KZ"])

    assert fake.connection_attempts == 1


class MultiStreamWebsocket:
    """Simulates a sequence of stream attempts with different outcomes."""

    def __init__(
        self,
        streams: Sequence[Sequence[dict[str, Any]] | Exception],
    ) -> None:
        self._streams = list(streams)
        self.connection_attempts = 0

    async def __aenter__(self) -> Self:
        self.connection_attempts += 1
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def quotes(
        self,
        symbols: Sequence[str],
    ) -> AsyncIterator[dict[str, Any]]:
        idx = min(self.connection_attempts - 1, len(self._streams) - 1)
        outcome = self._streams[idx]
        if isinstance(outcome, Exception):
            raise outcome
            yield  # pragma: no cover
        for message in outcome:
            yield message

    async def market_depth(
        self,
        symbol: str,
    ) -> AsyncIterator[dict[str, Any]]:
        idx = min(self.connection_attempts - 1, len(self._streams) - 1)
        outcome = self._streams[idx]
        if isinstance(outcome, Exception):
            raise outcome
            yield  # pragma: no cover
        for message in outcome:
            yield message


def test_without_reconnect_clean_eof_finishes_normally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A. reconnect=False + clean StopAsyncIteration finishes normally without retry."""
    messages = [{"c": "HSBK.KZ", "ltp": 100.0}]
    fake = FakeWebsocket(object(), messages=messages)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect(adapter, ["HSBK.KZ"])

    assert result == messages


def test_reconnect_reopens_stream_on_clean_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B. reconnect=True + clean StopAsyncIteration triggers reconnection."""
    stream1: list[dict[str, Any]] = []
    stream2 = [{"c": "HSBK.KZ", "ltp": 200.0}]
    fake = MultiStreamWebsocket([stream1, stream2])
    _install_fake_websocket(monkeypatch, fake)  # type: ignore[arg-type]
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect_reconnecting(adapter, ["HSBK.KZ"])

    assert result == stream2
    assert fake.connection_attempts == 2


def test_reconnect_reports_failed_and_resumed_on_clean_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """C. first stream EOF, second yields data: observer sees failed then resumed."""
    events: list[tuple[str, int, float]] = []
    stream1 = [{"c": "HSBK.KZ", "init": 1}]
    stream2 = [{"c": "HSBK.KZ", "init": 1, "ltp": 250.0}]
    fake = MultiStreamWebsocket([stream1, stream2])
    _install_fake_websocket(monkeypatch, fake)  # type: ignore[arg-type]
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    results: list[Any] = []

    async def run() -> None:
        async for msg in adapter.quotes(
            ["HSBK.KZ"],
            reconnect=True,
            observer=lambda ev, att, del_: events.append((ev, att, del_)),
        ):
            results.append(msg)
            if len(results) == 2:
                break

    asyncio.run(run())

    assert results == stream1 + stream2
    assert events == [("failed", 1, 1.0), ("resumed", 1, 0.0)]
    assert fake.connection_attempts == 2


def test_reconnect_backs_off_exponentially_on_repeated_clean_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D. repeated clean EOF: exponential retry delays are applied."""
    delays: list[float] = []
    fake = MultiStreamWebsocket([[], [], [], [{"c": "HSBK.KZ"}]])
    _install_fake_websocket(monkeypatch, fake)  # type: ignore[arg-type]

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", record_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    result = _collect_reconnecting(adapter, ["HSBK.KZ"])

    assert result == [{"c": "HSBK.KZ"}]
    assert delays == [1.0, 2.0, 4.0]
    assert fake.connection_attempts == 4


def test_reconnect_propagates_asyncio_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """G. asyncio cancellation propagates immediately without retrying."""
    fake = FakeWebsocket(object(), messages=[{"c": "HSBK.KZ"}])
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    async def run() -> None:
        async for _ in adapter.quotes(["HSBK.KZ"], reconnect=True):
            raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())


def test_scheduled_run_until_cancellation_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """H. scheduled _run_until cancellation terminates cleanly and does not reconnect."""
    stream_messages = [{"c": "HSBK.KZ", "ltp": 100.0}]
    fake = FakeWebsocket(object(), messages=stream_messages)
    _install_fake_websocket(monkeypatch, fake)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    collected: list[Any] = []

    async def consumer() -> None:
        async for quote in adapter.quotes(["HSBK.KZ"], reconnect=True):
            collected.append(quote)
            # After receiving quote, the stream ends and reconnect would sleep then retry;
            # simulate cancellation during that period.
            raise asyncio.CancelledError()

    async def run() -> None:
        try:
            await consumer()
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
    assert collected == stream_messages


def test_raht_orderbook_clean_termination_reconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduce the RAHT pattern: orderbook yields messages then cleanly ends.
    With reconnect=True the iterator must continue receiving from the next stream.
    """
    stream1 = [
        {"i": "RAHT.KZ", "n": 0, "ins": [{"p": 100, "q": 10, "s": "B"}]},
        {"i": "RAHT.KZ", "n": 1, "upd": [{"p": 100, "q": 20, "s": "B"}]},
    ]
    stream2 = [
        {"i": "RAHT.KZ", "n": 0, "ins": [{"p": 100, "q": 30, "s": "B"}]},
        {"i": "RAHT.KZ", "n": 1, "upd": [{"p": 100, "q": 40, "s": "B"}]},
    ]
    fake = MultiStreamWebsocket([stream1, stream2])
    _install_fake_websocket(monkeypatch, fake)  # type: ignore[arg-type]
    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", _no_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    collected: list[Any] = []

    async def run() -> None:
        async for msg in adapter.market_depth("RAHT.KZ", reconnect=True):
            collected.append(msg)
            if len(collected) == len(stream1) + len(stream2):
                break

    asyncio.run(run())

    assert collected == stream1 + stream2
    assert fake.connection_attempts == 2
