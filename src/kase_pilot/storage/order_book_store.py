"""Append-only storage for raw broker order-book stream messages."""

from __future__ import annotations

from typing import ClassVar

from kase_pilot.storage._stream_store import StreamStore


class OrderBookStore(StreamStore):
    """Append-only store for raw order-book (market depth) messages.

    Order-book messages are incremental diffs, not snapshots: each carries
    ``ins``/``del``/``upd`` arrays of price levels correlated by an opaque
    ``k`` key, and a single message is not a usable book on its own after
    the first (see docs/API_NOTES.md F-28). Reconstructing the book is
    therefore left to a later derived layer, working from this raw log.

    Note the ticker field differs from the quote stream: order-book
    messages use ``i``, not ``c``.
    """

    _TABLE: ClassVar[str] = "order_book_messages"
    _TICKER_FIELD: ClassVar[str] = "i"
    _STREAM: ClassVar[str] = "orderbook"
