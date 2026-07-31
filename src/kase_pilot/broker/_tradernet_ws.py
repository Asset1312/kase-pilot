"""Internal adapter for the officially linked Tradernet WebSocket client.

Confirmed live against a real account (see docs/API_NOTES.md, F-23/F-25/F-26):
transport, auth, and command/response framing are all implemented by
``tradernet.TradernetWebsocket`` and require no protocol code of our own.

This module is intentionally separate from ``_tradernet_sdk.py``: REST and
WebSocket are different protocols with different lifecycles (see
docs/BROKER_ARCHITECTURE.md §3.9). Neither imports the other.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from tradernet import Tradernet, TradernetWebsocket

from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class TradernetWebsocketAdapter:
    """Expose confirmed broker WebSocket streams through the SDK."""

    def __init__(self, client: Tradernet) -> None:
        self._client = client

    async def quotes(
        self,
        symbols: Sequence[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield live quote updates for the given symbols.

        Raises
        ------
        ApiRequestError
            If the WebSocket connection or the underlying SDK call fails.
        ValidationError
            If a yielded message is not a mapping.
        """
        try:
            async with TradernetWebsocket(self._client) as websocket:
                stream = websocket.quotes(symbols)
                while True:
                    try:
                        quote = await stream.__anext__()
                    except StopAsyncIteration:
                        return
                    except Exception as exc:
                        raise ApiRequestError(
                            "Tradernet WebSocket request failed"
                        ) from exc

                    if not isinstance(quote, Mapping):
                        raise ValidationError(
                            "Tradernet WebSocket returned a non-mapping quote message"
                        )

                    yield quote
        except ApiRequestError, ValidationError:
            raise
        except Exception as exc:
            raise ApiRequestError("Tradernet WebSocket request failed") from exc
