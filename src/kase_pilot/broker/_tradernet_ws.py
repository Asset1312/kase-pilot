"""Internal adapter for the officially linked Tradernet WebSocket client.

Confirmed live against a real account (see docs/API_NOTES.md, F-23/F-25/F-26):
transport, auth, and command/response framing are all implemented by
``tradernet.TradernetWebsocket`` and require no protocol code of our own.

This module is intentionally separate from ``_tradernet_sdk.py``: REST and
WebSocket are different protocols with different lifecycles (see
docs/BROKER_ARCHITECTURE.md §3.9). Neither imports the other.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from typing import Any

from tradernet import Tradernet, TradernetWebsocket

from kase_pilot.core.exceptions import ApiRequestError, ValidationError

# Backoff between reconnection attempts, in seconds: doubles up to a cap so a
# persistent outage does not hammer the broker, while a brief blip recovers
# quickly.
_INITIAL_RETRY_DELAY = 1.0
_MAX_RETRY_DELAY = 60.0

# Reported to the caller when a connection drops and when it is restored, so
# the CLI can surface it and the collector can record the gap. The broker
# layer itself neither prints nor writes to storage.
ReconnectObserver = Callable[[str, int, float], None]


class TradernetWebsocketAdapter:
    """Expose confirmed broker WebSocket streams through the SDK."""

    def __init__(self, client: Tradernet) -> None:
        self._client = client

    async def quotes(
        self,
        symbols: Sequence[str],
        *,
        reconnect: bool = False,
        observer: ReconnectObserver | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield live quote updates for the given symbols.

        Raises
        ------
        ApiRequestError
            If the WebSocket connection or the underlying SDK call fails and
            ``reconnect`` is disabled.
        ValidationError
            If a yielded message is not a mapping.
        """
        async for message in self._stream(
            lambda websocket: websocket.quotes(symbols),
            "quote",
            reconnect=reconnect,
            observer=observer,
        ):
            yield message

    async def market_depth(
        self,
        symbol: str,
        *,
        reconnect: bool = False,
        observer: ReconnectObserver | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield live order-book updates for the given symbol.

        Raises
        ------
        ApiRequestError
            If the WebSocket connection or the underlying SDK call fails and
            ``reconnect`` is disabled.
        ValidationError
            If a yielded message is not a mapping.
        """
        async for message in self._stream(
            lambda websocket: websocket.market_depth(symbol),
            "order-book",
            reconnect=reconnect,
            observer=observer,
        ):
            yield message

    async def _stream(
        self,
        make_stream: Callable[[TradernetWebsocket], AsyncIterator[Any]],
        message_name: str,
        *,
        reconnect: bool,
        observer: ReconnectObserver | None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Consume a stream, optionally reconnecting after transport failures.

        Only ``ApiRequestError`` (transport/connection trouble) triggers a
        retry. ``ValidationError`` means the broker sent something we do not
        understand — retrying would not help and would hide the problem.
        Cancellation is never caught.

        Note that after a reconnect the broker re-sends a fresh snapshot
        (``init: 1`` for quotes, ``n: 0`` for the order book — F-38/F-40), so
        a consumer rebuilding state does not need the messages lost during the
        outage; it needs to know the gap happened, which is what ``observer``
        reports.
        """
        if not reconnect:
            async for message in self._consume(make_stream, message_name):
                yield message
            return

        attempt = 0
        delay = _INITIAL_RETRY_DELAY
        while True:
            try:
                async for message in self._consume(make_stream, message_name):
                    if attempt:
                        if observer is not None:
                            observer("resumed", attempt, 0.0)
                        attempt = 0
                        delay = _INITIAL_RETRY_DELAY
                    yield message
                return
            except ApiRequestError:
                attempt += 1
                if observer is not None:
                    observer("failed", attempt, delay)
                await asyncio.sleep(delay)
                delay = min(delay * 2, _MAX_RETRY_DELAY)

    async def _consume(
        self,
        make_stream: Callable[[TradernetWebsocket], AsyncIterator[Any]],
        message_name: str,
    ) -> AsyncIterator[dict[str, Any]]:
        try:
            async with TradernetWebsocket(self._client) as websocket:
                stream = make_stream(websocket)
                while True:
                    try:
                        message = await stream.__anext__()
                    except StopAsyncIteration:
                        return
                    except Exception as exc:
                        raise ApiRequestError(
                            "Tradernet WebSocket request failed"
                        ) from exc

                    if not isinstance(message, Mapping):
                        raise ValidationError(
                            f"Tradernet WebSocket returned a non-mapping "
                            f"{message_name} message"
                        )

                    yield message
        except ApiRequestError, ValidationError:
            raise
        except Exception as exc:
            raise ApiRequestError("Tradernet WebSocket request failed") from exc
