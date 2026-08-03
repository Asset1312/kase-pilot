"""Append-only SQLite storage for raw broker quote stream messages.

Design rationale (see docs/API_NOTES.md F-27):

Quote messages are *partial deltas* — a message may carry 8 of ~70 fields,
and only ``c`` (the ticker) is confirmed present on every message. Storing a
merged "current state" would bake our interpretation of the delta semantics
into the data irreversibly, and no complete contract for those semantics is
confirmed. This module therefore stores each message verbatim, append-only.
Any derived view (candles, point-in-time snapshots) can be rebuilt from this
log later, and rebuilt again if our understanding changes.

Two timestamps matter and are kept distinct:

- ``received_at`` — this process's own clock, UTC, recorded here.
- the broker's ``acc_srv_tm`` — preserved inside ``payload``, untouched,
  because its format and timezone are not confirmed.

Collector sessions are recorded separately so that gaps in the data (periods
when nothing was running) are visible rather than silently indistinguishable
from periods when the market produced no messages.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

_SCHEMA = """
CREATE TABLE IF NOT EXISTS quote_messages (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    received_at TEXT NOT NULL,
    session_id  INTEGER NOT NULL,
    payload     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);

CREATE INDEX IF NOT EXISTS quote_messages_ticker_received_at
    ON quote_messages (ticker, received_at);

CREATE TABLE IF NOT EXISTS collector_sessions (
    id           INTEGER PRIMARY KEY,
    stream       TEXT NOT NULL,
    symbols      TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class QuoteStore:
    """Append-only store for raw quote messages, backed by SQLite.

    Use as a context manager; the collector session is opened on entry and
    closed on exit, so an interrupted run still records when it stopped.
    """

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._connection: sqlite3.Connection | None = None
        self._session_id: int | None = None
        self._stream = ""
        self._symbols: tuple[str, ...] = ()

    def open_session(self, stream: str, symbols: tuple[str, ...]) -> Self:
        """Record what this collector run is about, before entering it."""
        self._stream = stream
        self._symbols = symbols
        return self

    def __enter__(self) -> Self:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._database_path)
        connection.executescript(_SCHEMA)
        cursor = connection.execute(
            "INSERT INTO collector_sessions (stream, symbols, started_at) "
            "VALUES (?, ?, ?)",
            (self._stream, json.dumps(list(self._symbols)), _utc_now()),
        )
        connection.commit()
        self._connection = connection
        self._session_id = cursor.lastrowid
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is None:
            return
        self._connection.execute(
            "UPDATE collector_sessions SET finished_at = ? WHERE id = ?",
            (_utc_now(), self._session_id),
        )
        self._connection.commit()
        self._connection.close()
        self._connection = None

    def save(self, message: Mapping[str, Any]) -> None:
        """Append one raw quote message verbatim.

        The message is stored as received. Only ``c`` (ticker) is extracted
        into its own column, because it is the one field confirmed present on
        every quote message (F-27); everything else stays in ``payload``.
        """
        if self._connection is None:
            raise RuntimeError("QuoteStore must be used as a context manager")

        ticker = message.get("c")
        self._connection.execute(
            "INSERT INTO quote_messages "
            "(ticker, received_at, session_id, payload) VALUES (?, ?, ?, ?)",
            (
                ticker if isinstance(ticker, str) else "",
                _utc_now(),
                self._session_id,
                json.dumps(message, ensure_ascii=False),
            ),
        )
        self._connection.commit()
