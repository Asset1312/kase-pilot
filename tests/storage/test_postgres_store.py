"""Tests for the PostgreSQL append-only stream store."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from kase_pilot.storage._postgres_store import PostgresStreamStore
from kase_pilot.storage.factory import create_stream_backend

# We skip all tests in this file if POSTGRES_URI is not provided.
pytestmark = pytest.mark.skipif(
    "TEST_POSTGRES_URI" not in os.environ,
    reason="TEST_POSTGRES_URI is not set",
)


def _get_uri() -> str:
    return os.environ["TEST_POSTGRES_URI"]


def _clean_tables(uri: str) -> None:
    import psycopg

    with psycopg.connect(uri, autocommit=True) as conn, conn.cursor() as cur:
            cur.execute(
                "DROP TABLE IF EXISTS quote_messages, order_book_messages, collector_interruptions, collector_sessions CASCADE"
            )


@pytest.fixture(autouse=True)
def clean_db() -> None:
    _clean_tables(_get_uri())
    yield
    _clean_tables(_get_uri())


def _rows(query: str, args: tuple = ()) -> list[tuple[object, ...]]:
    import psycopg

    with psycopg.connect(_get_uri()) as conn, conn.cursor() as cur:
        cur.execute(query, args)
        return list(cur.fetchall())


def test_creates_tables_and_stores_verbatim() -> None:
    uri = _get_uri()
    store = PostgresStreamStore(
        uri=uri,
        table="quote_messages",
        ticker_field="c",
        stream="quotes",
    )

    message = {
        "c": "HSBK.KZ",
        "ltp": 383.83,
        "name": "Народный банк Казахстана",
        "nested": {"unknown": [True, None]},
    }

    with store.open_session(("HSBK.KZ",)):
        store.save(message)

    rows = _rows("SELECT ticker, payload FROM quote_messages")
    assert len(rows) == 1
    ticker, payload = rows[0]
    assert ticker == "HSBK.KZ"
    assert json.loads(payload) == message


def test_records_session_start_and_finish() -> None:
    uri = _get_uri()
    store = PostgresStreamStore(
        uri=uri,
        table="quote_messages",
        ticker_field="c",
        stream="quotes",
    )

    with store.open_session(("HSBK.KZ", "KSPI.KZ")):
        pass

    rows = _rows(
        "SELECT stream, symbols, started_at, finished_at FROM collector_sessions"
    )
    assert len(rows) == 1
    stream, symbols, started_at, finished_at = rows[0]
    assert stream == "quotes"
    assert json.loads(symbols) == ["HSBK.KZ", "KSPI.KZ"]
    assert started_at
    assert finished_at


def test_records_interruption_so_gaps_are_visible() -> None:
    uri = _get_uri()
    store = PostgresStreamStore(
        uri=uri,
        table="quote_messages",
        ticker_field="c",
        stream="quotes",
    )

    with store.open_session(("HSBK.KZ",)):
        store.save({"c": "HSBK.KZ"})
        store.record_interruption(1)

    rows = _rows("SELECT attempt, failed_at, resumed_at FROM collector_interruptions")
    assert len(rows) == 1
    attempt, failed_at, resumed_at = rows[0]
    assert attempt == 1
    assert failed_at
    assert resumed_at is None


def test_credentials_are_not_leaked_on_connection_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Use an invalid URI to force a connection error
    store = PostgresStreamStore(
        uri="postgresql://fakeuser:secretpassword@localhost:5432/fakedb",
        table="quote_messages",
        ticker_field="c",
        stream="quotes",
    )

    with pytest.raises(RuntimeError) as exc_info, store.open_session(("HSBK.KZ",)):
        pass

    assert "Failed to connect to PostgreSQL backend." in str(exc_info.value)
    assert "secretpassword" not in str(exc_info.value)
    assert exc_info.value.__cause__ is None


def test_factory_selects_postgres_when_env_var_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("POSTGRES_URI", "postgresql://dummy")
    backend = create_stream_backend(
        database_path=tmp_path / "dummy.sqlite3",
        table="test_table",
        ticker_field="test_field",
        stream="test_stream",
    )
    assert isinstance(backend, PostgresStreamStore)


def test_factory_selects_sqlite_when_env_var_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("POSTGRES_URI", raising=False)
    backend = create_stream_backend(
        database_path=tmp_path / "dummy.sqlite3",
        table="test_table",
        ticker_field="test_field",
        stream="test_stream",
    )
    from kase_pilot.storage._sqlite_store import SqliteStreamStore

    assert isinstance(backend, SqliteStreamStore)
