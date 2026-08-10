"""Append-only PostgreSQL storage for raw broker stream data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from types import TracebackType

# We import psycopg lazily when entering the session to prevent module-level
# import errors if the dependency is somehow not installed but PostgreSQL is
# not configured to be used.
# However, type checking needs it.
from typing import TYPE_CHECKING, Any, Self

if TYPE_CHECKING:
    import psycopg


_SCHEMA = """
CREATE TABLE IF NOT EXISTS collector_sessions (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stream       TEXT NOT NULL,
    symbols      TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT
);

CREATE TABLE IF NOT EXISTS quote_messages (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker      TEXT NOT NULL,
    received_at TEXT NOT NULL,
    session_id  BIGINT NOT NULL,
    payload     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);

CREATE INDEX IF NOT EXISTS quote_messages_ticker_received_at
    ON quote_messages (ticker, received_at);

CREATE TABLE IF NOT EXISTS order_book_messages (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker      TEXT NOT NULL,
    received_at TEXT NOT NULL,
    session_id  BIGINT NOT NULL,
    payload     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);

CREATE INDEX IF NOT EXISTS order_book_messages_ticker_received_at
    ON order_book_messages (ticker, received_at);

CREATE TABLE IF NOT EXISTS collector_interruptions (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id  BIGINT NOT NULL,
    attempt     BIGINT NOT NULL,
    failed_at   TEXT NOT NULL,
    resumed_at  TEXT,
    FOREIGN KEY (session_id) REFERENCES collector_sessions (id)
);
"""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class PostgresStreamStore:
    """Append-only store for one raw broker stream, backed by PostgreSQL.

    Matches the exact semantics and JSON/TEXT payload structures of the SQLite
    backend. Requires POSTGRES_URI to connect. Opens connection lazily.
    """

    def __init__(
        self,
        uri: str,
        table: str,
        ticker_field: str,
        stream: str,
    ) -> None:
        self._uri = uri
        self._table = table
        self._ticker_field = ticker_field
        self._stream = stream
        self._connection: psycopg.Connection[Any] | None = None
        self._session_id: int | None = None
        self._symbols: tuple[str, ...] = ()

    def open_session(self, symbols: tuple[str, ...]) -> Self:
        self._symbols = symbols
        return self

    def __enter__(self) -> Self:
        try:
            import psycopg
        except ImportError:
            raise RuntimeError(
                "psycopg is not installed. Required for PostgreSQL backend."
            ) from None

        try:
            connection = psycopg.connect(self._uri, autocommit=True)
        except Exception:  # noqa: BLE001
            # We catch Exception, not just psycopg.Error, to absolutely guarantee
            # the URI isn't leaked in any unexpected exception traceback.
            raise RuntimeError("Failed to connect to PostgreSQL backend.") from None

        try:
            connection.execute(_SCHEMA)
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO collector_sessions (stream, symbols, started_at) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (self._stream, json.dumps(list(self._symbols)), _utc_now()),
                )
                row = cursor.fetchone()
                assert row is not None
                self._session_id = row[0]
            self._connection = connection
            return self
        except Exception:  # noqa: BLE001
            connection.close()
            raise RuntimeError(
                "Failed to initialize PostgreSQL backend session."
            ) from None

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._connection is None:
            return
        try:
            self._connection.execute(
                "UPDATE collector_sessions SET finished_at = %s WHERE id = %s",
                (_utc_now(), self._session_id),
            )
        except Exception:  # noqa: BLE001, S110
            pass  # Avoid leaking errors on exit
        finally:
            self._connection.close()
            self._connection = None

    def save(self, message: Mapping[str, Any]) -> None:
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        ticker = message.get(self._ticker_field)
        # Using %s for parameterized values in psycopg
        try:
            self._connection.execute(
                f"INSERT INTO {self._table} "
                "(ticker, received_at, session_id, payload) VALUES (%s, %s, %s, %s)",
                (
                    ticker if isinstance(ticker, str) else "",
                    _utc_now(),
                    self._session_id,
                    json.dumps(message, ensure_ascii=False),
                ),
            )
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                "Failed to save message to PostgreSQL backend."
            ) from None

    def record_interruption(self, attempt: int) -> None:
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        try:
            self._connection.execute(
                "INSERT INTO collector_interruptions (session_id, attempt, failed_at) "
                "VALUES (%s, %s, %s)",
                (self._session_id, attempt, _utc_now()),
            )
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                "Failed to record interruption in PostgreSQL backend."
            ) from None

    def record_resumption(self) -> None:
        if self._connection is None:
            raise RuntimeError(
                f"{type(self).__name__} must be used as a context manager"
            )

        try:
            self._connection.execute(
                "UPDATE collector_interruptions SET resumed_at = %s "
                "WHERE session_id = %s AND resumed_at IS NULL",
                (_utc_now(), self._session_id),
            )
        except Exception:  # noqa: BLE001
            raise RuntimeError(
                "Failed to record resumption in PostgreSQL backend."
            ) from None
