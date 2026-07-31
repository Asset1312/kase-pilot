"""Tests for the internal Tradernet WebSocket adapter."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, Self

import pytest

import kase_pilot.broker._tradernet_ws as tradernet_ws
from kase_pilot.broker._tradernet_ws import TradernetWebsocketAdapter
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


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
