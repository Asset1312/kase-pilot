"""Shared append-only SQLite storage for raw broker stream messages.

Design rationale (see docs/API_NOTES.md F-27, F-28, F-38):

Stream messages are *partial updates*, not self-contained records. Quote
messages may carry as few as 7 of ~90 fields and sometimes no price at all;
order-book messages are explicit positional ``ins``/``del``/``upd`` diffs.
Merging either into a "current state" at write time would bake protocol
interpretation into the data irreversibly. Every stream is therefore stored
verbatim, append-only, and any derived view is rebuilt from this log later —
and can be rebuilt again when understanding improves.

Two timestamps are kept distinct, never conflated (F-39):

- ``received_at`` — this process's own clock, UTC, recorded here.
- the broker's own timestamp — left untouched inside ``payload``, because
  its timezone is not declared and differs from both the instrument's
  market timezone and UTC.

Collector sessions are recorded so that gaps (periods when nothing was
running) are visible, rather than indistinguishable from a quiet market.
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
CREATE TABLE IF NOT EXISTS collector_sessions (
    id           INTEGER PRIMARY KEY,
    stream       TEXT NOT NULL,
    symbols      TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);

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

CREATE TABLE IF NOT EXISTS order_book_messages (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    received_at TEXT NOT NULL,
    session_id  INTEGER NOT NULL,
    payload     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);

CREATE INDEX IF NOT EXISTS order_book_messages_ticker_received_at
    ON order_book_messages (ticker, received_at);

CREATE TABLE IF NOT EXISTS collector_interruptions (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL,
    attempt     INTEGER NOT NULL,
    failed_at   TEXT NOT NULL,
    resumed_at  TEXT,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SqliteStreamStore:
    """Append-only store for one raw broker stream, backed by SQLite.

    Use as a context manager; the session is opened on entry and closed on
    exit, so an interrupted run still records when it stopped.
    """

    def __init__(
        self,
        database_path: Path,
        table: str,
        ticker_field: str,
        stream: str,
    ) -> None:
        self._database_path = database_path
        self._table = table
        self._ticker_field = ticker_field
        self._stream = stream
        self._connection: sqlite3.Connection | None = None
        self._session_id: int | None = None
        self._symbols: tuple[str, ...] = ()

    def open_session(self, symbols: tuple[str, ...]) -> Self:
        """Record what this collector run covers, before entering it."""
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
        """Append one raw stream message verbatim.

        Only the ticker is lifted into its own column, for querying; every
        other field stays in ``payload`` exactly as received.
        """
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        ticker = message.get(self._ticker_field)
        # Table name is passed dynamically, but internally controlled. We trust it.
        self._connection.execute(
            f"INSERT INTO {self._table} "
            "(ticker, received_at, session_id, payload) VALUES (?, ?, ?, ?)",
            (
                ticker if isinstance(ticker, str) else "",
                _utc_now(),
                self._session_id,
                json.dumps(message, ensure_ascii=False),
            ),
        )
        self._connection.commit()

    def record_interruption(self, attempt: int) -> None:
        """Record that the connection dropped and a retry is pending.

        Without this, an outage is indistinguishable from a quiet market: the
        message log simply has no rows for that period. Recording it makes the
        gap explicit and queryable.
        """
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        self._connection.execute(
            "INSERT INTO collector_interruptions (session_id, attempt, failed_at) "
            "VALUES (?, ?, ?)",
            (self._session_id, attempt, _utc_now()),
        )
        self._connection.commit()

    def record_resumption(self) -> None:
        """Close out the open interruption for this session, if any."""
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        self._connection.execute(
            "UPDATE collector_interruptions SET resumed_at = ? "
            "WHERE session_id = ? AND resumed_at IS NULL",
            (_utc_now(), self._session_id),
        )
        self._connection.commit()
