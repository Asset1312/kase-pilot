"""Tests for the append-only order-book store."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from kase_pilot.storage import OrderBookStore, QuoteStore


def _rows(database_path: Path, query: str) -> list[tuple[object, ...]]:
    connection = sqlite3.connect(database_path)
    try:
        return list(connection.execute(query))
    finally:
        connection.close()


def test_stores_message_payload_verbatim(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    message = {
        "n": 0,
        "i": "HSBK.KZ",
        "min_step": None,
        "del": [],
        "ins": [
            {"p": 383.96, "s": "S", "q": 249, "k": 0},
            {"p": 383.8, "s": "B", "q": 21, "k": 1},
        ],
        "upd": [],
        "cnt": 2,
        "x": 1,
    }

    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store:
        store.save(message)

    ((ticker, payload),) = _rows(
        database_path, "SELECT ticker, payload FROM order_book_messages"
    )
    assert ticker == "HSBK.KZ"
    assert json.loads(payload) == message


def test_ticker_is_read_from_i_not_c(tmp_path: Path) -> None:
    """Order-book messages carry the ticker in ``i``, unlike quotes (F-28)."""
    database_path = tmp_path / "market.sqlite3"

    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store:
        store.save({"i": "HSBK.KZ", "c": "SHOULD_BE_IGNORED", "ins": []})

    ((ticker,),) = _rows(database_path, "SELECT ticker FROM order_book_messages")
    assert ticker == "HSBK.KZ"


def test_incremental_diff_message_is_stored_as_is(tmp_path: Path) -> None:
    """del/ins/upd diffs must survive untouched for later reconstruction."""
    database_path = tmp_path / "market.sqlite3"
    diff = {
        "n": 1,
        "i": "HSBK.KZ",
        "del": [{"p": 383.8, "k": 1}, {"p": 383.96, "k": 0}],
        "ins": [{"p": 383.98, "s": "S", "q": 974, "k": 0}],
        "upd": [],
        "cnt": 2,
        "x": 1,
    }

    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store:
        store.save(diff)

    ((payload,),) = _rows(database_path, "SELECT payload FROM order_book_messages")
    assert json.loads(payload) == diff


def test_appends_rather_than_overwriting(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    first = {"i": "HSBK.KZ", "n": 0}
    second = {"i": "HSBK.KZ", "n": 1}

    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store:
        store.save(first)
        store.save(second)

    rows = _rows(database_path, "SELECT payload FROM order_book_messages ORDER BY id")
    assert [json.loads(payload) for (payload,) in rows] == [first, second]


def test_records_session_with_orderbook_stream_name(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"

    with OrderBookStore(database_path).open_session(("HSBK.KZ",)):
        pass

    ((stream, symbols, started_at, finished_at),) = _rows(
        database_path,
        "SELECT stream, symbols, started_at, finished_at FROM collector_sessions",
    )
    assert stream == "orderbook"
    assert json.loads(symbols) == ["HSBK.KZ"]
    assert started_at
    assert finished_at


def test_session_is_closed_even_when_collector_fails(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"

    with (
        pytest.raises(RuntimeError),
        OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store,
    ):
        store.save({"i": "HSBK.KZ"})
        raise RuntimeError("stream dropped")

    ((finished_at,),) = _rows(
        database_path, "SELECT finished_at FROM collector_sessions"
    )
    assert finished_at


def test_save_without_context_manager_is_rejected(tmp_path: Path) -> None:
    store = OrderBookStore(tmp_path / "market.sqlite3").open_session(())

    with pytest.raises(RuntimeError, match="context manager"):
        store.save({"i": "HSBK.KZ"})


def test_shares_database_with_quote_store_without_collision(tmp_path: Path) -> None:
    """Both streams live in one database file, in separate tables."""
    database_path = tmp_path / "market.sqlite3"

    with QuoteStore(database_path).open_session(("HSBK.KZ",)) as quotes:
        quotes.save({"c": "HSBK.KZ", "ltp": 383.83})
    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as book:
        book.save({"i": "HSBK.KZ", "ins": []})

    ((quote_count,),) = _rows(database_path, "SELECT COUNT(*) FROM quote_messages")
    ((book_count,),) = _rows(database_path, "SELECT COUNT(*) FROM order_book_messages")
    streams = _rows(database_path, "SELECT stream FROM collector_sessions ORDER BY id")

    assert quote_count == 1
    assert book_count == 1
    assert [stream for (stream,) in streams] == ["quotes", "orderbook"]
