"""Append-only storage for raw broker quote stream messages."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Any, ClassVar, Self

from kase_pilot.storage.factory import create_stream_backend


class QuoteStore:
    """Append-only store for raw quote messages.

    Quote messages are partial deltas: a message may carry as few as 7 of
    ~90 fields and sometimes no price at all (see docs/API_NOTES.md F-27,
    F-38). Only ``c`` — the ticker — is confirmed present on every message,
    so it is the only field lifted into its own column.
    """

    _TABLE: ClassVar[str] = "quote_messages"
    _TICKER_FIELD: ClassVar[str] = "c"
    _STREAM: ClassVar[str] = "quotes"

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
