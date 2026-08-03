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
) -> list[Any]:
    async def run() -> list[Any]:
        return [
            quote
            async for quote in adapter.quotes(
                symbols, reconnect=True, observer=observer
            )
        ]

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
    fake = FlakyWebsocket(failures=3, messages=[])
    _install_fake_websocket(monkeypatch, fake)

    async def record_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(tradernet_ws.asyncio, "sleep", record_sleep)
    adapter = TradernetWebsocketAdapter(object())  # type: ignore[arg-type]

    _collect_reconnecting(adapter, ["HSBK.KZ"])

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
