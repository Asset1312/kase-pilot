"""Centralized factory for stream storage backends."""

from __future__ import annotations

import os
from pathlib import Path

from kase_pilot.storage._postgres_store import PostgresStreamStore
from kase_pilot.storage._sqlite_store import SqliteStreamStore
from kase_pilot.storage.base import StreamBackend


def create_stream_backend(
    database_path: Path,
    table: str,
    ticker_field: str,
    stream: str,
) -> StreamBackend:
    """Create the appropriate stream storage backend.

    If POSTGRES_URI is present in the environment, returns a PostgreSQL backend.
    Otherwise, returns the default SQLite backend.
    """
    postgres_uri = os.environ.get("POSTGRES_URI")
    if postgres_uri:
        return PostgresStreamStore(
            uri=postgres_uri,
            table=table,
            ticker_field=ticker_field,
            stream=stream,
        )

    return SqliteStreamStore(
        database_path=database_path,
        table=table,
        ticker_field=ticker_field,
        stream=stream,
    )
