"""Append-only storage for raw broker order-book stream messages."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, Self

from kase_pilot.storage.factory import create_stream_backend


class OrderBookStore:
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

    def __init__(self, database_path: Path) -> None:
        self._backend = create_stream_backend(
            database_path=database_path,
            table=self._TABLE,
            ticker_field=self._TICKER_FIELD,
            stream=self._STREAM,
        )

    def open_session(self, symbols: tuple[str, ...]) -> Self:
        self._backend.open_session(symbols)
        return self

    def __enter__(self) -> Self:
        self._backend.__enter__()
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._backend.__exit__(exception_type, exception_value, traceback)

    def save(self, message: Mapping[str, Any]) -> None:
        self._backend.save(message)

    def record_interruption(self, attempt: int) -> None:
        self._backend.record_interruption(attempt)

    def record_resumption(self) -> None:
        self._backend.record_resumption()
