"""Append-only storage for raw broker quote stream messages."""

from __future__ import annotations

from typing import ClassVar

from kase_pilot.storage._stream_store import StreamStore


class QuoteStore(StreamStore):
    """Append-only store for raw quote messages.

    Quote messages are partial deltas: a message may carry as few as 7 of
    ~90 fields and sometimes no price at all (see docs/API_NOTES.md F-27,
    F-38). Only ``c`` — the ticker — is confirmed present on every message,
    so it is the only field lifted into its own column.
    """

    _TABLE: ClassVar[str] = "quote_messages"
    _TICKER_FIELD: ClassVar[str] = "c"
    _STREAM: ClassVar[str] = "quotes"
