"""Tests for the append-only quote store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from kase_pilot.storage import QuoteStore


def _rows(database_path: Path, query: str) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(database_path)
    try:
        return list(connection.execute(query))
    finally:
        connection.close()


def test_creates_database_file_and_parent_directory(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "market.sqlite3"

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)):
        pass

    assert database_path.is_file()


def test_stores_message_payload_verbatim(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    message = {
        "c": "HSBK.KZ",
        "ltp": 383.83,
        "name": "Народный банк Казахстана",
        "nested": {"unknown": [True, None]},
    }

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save(message)

    rows = _rows(database_path, "SELECT ticker, payload FROM quote_messages")
    assert len(rows) == 1
    ticker, payload = rows[0]
    assert ticker == "HSBK.KZ"
    assert json.loads(payload) == message


def test_appends_rather_than_overwriting(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    first = {"c": "HSBK.KZ", "ltp": 383.83}
    second = {"c": "HSBK.KZ", "ltp": 384.0}

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save(first)
        store.save(second)

    rows = _rows(database_path, "SELECT payload FROM quote_messages ORDER BY id")
    assert [json.loads(payload) for (payload,) in rows] == [first, second]


def test_partial_delta_message_is_stored_as_is(tmp_path: Path) -> None:
    """Quote messages are partial deltas (F-27); nothing may be filled in."""
    database_path = tmp_path / "market.sqlite3"
    delta = {"c": "HSBK.KZ", "n": 2275, "rev": 32375194}

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save(delta)

    ((payload,),) = _rows(database_path, "SELECT payload FROM quote_messages")
    assert json.loads(payload) == delta


def test_message_without_ticker_is_still_stored(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    message = {"unexpected": "shape"}

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save(message)

    ((ticker, payload),) = _rows(
        database_path, "SELECT ticker, payload FROM quote_messages"
    )
    assert ticker == ""
    assert json.loads(payload) == message


def test_records_session_start_and_finish(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ", "KSPI.KZ")):
        pass

    ((stream, symbols, started_at, finished_at),) = _rows(
        database_path,
        "SELECT stream, symbols, started_at, finished_at FROM collector_sessions",
    )
    assert stream == "quotes"
    assert json.loads(symbols) == ["HSBK.KZ", "KSPI.KZ"]
    assert started_at
    assert finished_at


def test_session_is_closed_even_when_collector_fails(tmp_path: Path) -> None:
    """An interrupted run must still record when it stopped, so gaps show."""
    database_path = tmp_path / "market.sqlite3"

    with (
        pytest.raises(RuntimeError),
        QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store,
    ):
        store.save({"c": "HSBK.KZ"})
        raise RuntimeError("stream dropped")

    ((finished_at,),) = _rows(
        database_path, "SELECT finished_at FROM collector_sessions"
    )
    assert finished_at


def test_messages_are_linked_to_their_session(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save({"c": "HSBK.KZ"})
    with QuoteStore(database_path).open_session("quotes", ("KSPI.KZ",)) as store:
        store.save({"c": "KSPI.KZ"})

    rows = _rows(
        database_path, "SELECT ticker, session_id FROM quote_messages ORDER BY id"
    )
    assert [ticker for ticker, _ in rows] == ["HSBK.KZ", "KSPI.KZ"]
    assert rows[0][1] != rows[1][1]


def test_second_run_reuses_existing_database(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save({"c": "HSBK.KZ", "ltp": 1})
    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save({"c": "HSBK.KZ", "ltp": 2})

    ((count,),) = _rows(database_path, "SELECT COUNT(*) FROM quote_messages")
    assert count == 2
    ((sessions,),) = _rows(database_path, "SELECT COUNT(*) FROM collector_sessions")
    assert sessions == 2


def test_received_at_is_recorded_separately_from_broker_time(tmp_path: Path) -> None:
    """Our clock and the broker's acc_srv_tm must not be conflated."""
    database_path = tmp_path / "market.sqlite3"
    message = {"c": "HSBK.KZ", "acc_srv_tm": "2026-07-31 12:56:15.127"}

    with QuoteStore(database_path).open_session("quotes", ("HSBK.KZ",)) as store:
        store.save(message)

    ((received_at, payload),) = _rows(
        database_path, "SELECT received_at, payload FROM quote_messages"
    )
    assert received_at != message["acc_srv_tm"]
    assert json.loads(payload)["acc_srv_tm"] == message["acc_srv_tm"]


def test_save_without_context_manager_is_rejected(tmp_path: Path) -> None:
    store = QuoteStore(tmp_path / "market.sqlite3").open_session("quotes", ())

    with pytest.raises(RuntimeError, match="context manager"):
        store.save({"c": "HSBK.KZ"})
