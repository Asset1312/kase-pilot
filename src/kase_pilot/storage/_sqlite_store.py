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
import time
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

# SQLite permits only one writer at a time.  Give short collector transactions
# enough time to wait for that writer instead of failing immediately.  This value
# configures both sqlite3.connect(timeout=...) and PRAGMA busy_timeout.
SQLITE_BUSY_TIMEOUT_MS = 30_000
_LOCK_RETRY_ATTEMPTS = 3
_LOCK_RETRY_BASE_SECONDS = 0.05

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
        connection = sqlite3.connect(
            self._database_path,
            timeout=SQLITE_BUSY_TIMEOUT_MS / 1_000,
        )
        try:
            self._configure_connection(connection)
            self._retry_locked(lambda: connection.executescript(_SCHEMA), connection)
            cursor = self._execute_and_commit(
                connection,
                "INSERT INTO collector_sessions (stream, symbols, started_at) "
                "VALUES (?, ?, ?)",
                (self._stream, json.dumps(list(self._symbols)), _utc_now()),
            )
        except BaseException:
            connection.close()
            raise
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
        connection = self._connection
        try:
            self._execute_and_commit(
                connection,
                "UPDATE collector_sessions SET finished_at = ? WHERE id = ?",
                (_utc_now(), self._session_id),
            )
        finally:
            connection.close()
            self._connection = None
            self._session_id = None

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
        self._execute_and_commit(
            self._connection,
            f"INSERT INTO {self._table} "
            "(ticker, received_at, session_id, payload) VALUES (?, ?, ?, ?)",
            (
                ticker if isinstance(ticker, str) else "",
                _utc_now(),
                self._session_id,
                json.dumps(message, ensure_ascii=False),
            ),
        )

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

        self._execute_and_commit(
            self._connection,
            "INSERT INTO collector_interruptions (session_id, attempt, failed_at) "
            "VALUES (?, ?, ?)",
            (self._session_id, attempt, _utc_now()),
        )

    def record_resumption(self) -> None:
        """Close out the open interruption for this session, if any."""
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        self._execute_and_commit(
            self._connection,
            "UPDATE collector_interruptions SET resumed_at = ? "
            "WHERE session_id = ? AND resumed_at IS NULL",
            (_utc_now(), self._session_id),
        )

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        """Configure one process-local connection for concurrent appends.

        WAL allows readers and the active writer to proceed concurrently.  NORMAL
        synchronous mode keeps WAL transactions durable across application/process
        crashes while avoiding the extra checkpoint sync of FULL; a host power loss
        can still lose the most recently committed WAL transaction.
        """
        connection.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        current_row = connection.execute("PRAGMA journal_mode").fetchone()
        current_mode = str(current_row[0]).lower() if current_row else ""
        if current_mode != "wal":
            mode_row = SqliteStreamStore._retry_locked(
                lambda: connection.execute("PRAGMA journal_mode=WAL").fetchone(),
                connection,
            )
            current_mode = str(mode_row[0]).lower() if mode_row else ""
        if current_mode != "wal":
            raise sqlite3.OperationalError(
                f"SQLite WAL journal mode is unavailable (got {current_mode!r})"
            )
        connection.execute("PRAGMA synchronous=NORMAL")

    @staticmethod
    def _execute_and_commit(
        connection: sqlite3.Connection,
        sql: str,
        parameters: tuple[object, ...],
    ) -> sqlite3.Cursor:
        """Execute one bounded transaction without duplicating a committed row."""

        def transaction() -> sqlite3.Cursor:
            cursor = connection.execute(sql, parameters)
            connection.commit()
            return cursor

        return SqliteStreamStore._retry_locked(transaction, connection)

    @staticmethod
    def _retry_locked(
        operation: Callable[[], Any],
        connection: sqlite3.Connection,
    ) -> Any:
        """Retry only SQLite's transient writer-lock errors.

        sqlite3's busy handler gets the first chance to wait.  If it still reports
        SQLITE_BUSY/SQLITE_LOCKED, roll back the uncommitted attempt and retry with
        a small deterministic backoff.  Successful commits return without retry,
        so an acknowledged row cannot be inserted twice.
        """
        for retry_index in range(_LOCK_RETRY_ATTEMPTS):
            try:
                return operation()
            except sqlite3.OperationalError as error:
                if not _is_transient_lock(error):
                    raise
                with suppress(sqlite3.Error):
                    connection.rollback()
                if retry_index + 1 == _LOCK_RETRY_ATTEMPTS:
                    raise
                time.sleep(_LOCK_RETRY_BASE_SECONDS * (retry_index + 1))
        raise AssertionError("unreachable SQLite retry state")


def _is_transient_lock(error: sqlite3.OperationalError) -> bool:
    error_code = getattr(error, "sqlite_errorcode", None)
    if isinstance(error_code, int):
        return error_code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    return str(error).lower() in {
        "database is locked",
        "database table is locked",
        "database schema is locked",
    }
