"""Tests for rebuilding point-in-time state from the raw stream log."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kase_pilot.derive import rebuild_order_book, rebuild_quote
from kase_pilot.storage import OrderBookStore, QuoteStore


def _store_quotes(database_path: Path, messages: list[dict[str, Any]]) -> None:
    with QuoteStore(database_path).open_session(("HSBK.KZ",)) as store:
        for message in messages:
            store.save(message)


def _store_book(database_path: Path, messages: list[dict[str, Any]]) -> None:
    with OrderBookStore(database_path).open_session(("HSBK.KZ",)) as store:
        for message in messages:
            store.save(message)


def test_rebuild_quote_returns_none_when_nothing_collected(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_quotes(database_path, [{"c": "HSBK.KZ"}])

    assert rebuild_quote(database_path, "KSPI.KZ") is None


def test_rebuild_quote_merges_deltas_onto_the_snapshot(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_quotes(
        database_path,
        [
            {"c": "HSBK.KZ", "init": 1, "ltp": 383.83, "bbp": 383.67, "name": "Halyk"},
            {"c": "HSBK.KZ", "init": 0, "bbp": 384.10},
            {"c": "HSBK.KZ", "init": 0, "ltp": 384.49},
        ],
    )

    state = rebuild_quote(database_path, "HSBK.KZ")

    assert state is not None
    assert state["ltp"] == 384.49
    assert state["bbp"] == 384.10
    assert state["name"] == "Halyk"
    assert state["_from_snapshot"] is True
    assert state["_messages_applied"] == 3


def test_rebuild_quote_restarts_from_the_latest_snapshot(tmp_path: Path) -> None:
    """Fields from before a reconnect must not leak into the result."""
    database_path = tmp_path / "market.sqlite3"
    _store_quotes(
        database_path,
        [
            {"c": "HSBK.KZ", "init": 1, "ltp": 1.0, "stale_field": "from first block"},
            {"c": "HSBK.KZ", "init": 0, "ltp": 2.0},
            {"c": "HSBK.KZ", "init": 1, "ltp": 3.0},
            {"c": "HSBK.KZ", "init": 0, "ltp": 4.0},
        ],
    )

    state = rebuild_quote(database_path, "HSBK.KZ")

    assert state is not None
    assert state["ltp"] == 4.0
    assert "stale_field" not in state
    assert state["_messages_applied"] == 2


def test_rebuild_quote_reports_when_no_snapshot_was_captured(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_quotes(
        database_path,
        [
            {"c": "HSBK.KZ", "init": 0, "bbp": 383.67},
            {"c": "HSBK.KZ", "init": 0, "ltp": 384.49},
        ],
    )

    state = rebuild_quote(database_path, "HSBK.KZ")

    assert state is not None
    assert state["_from_snapshot"] is False
    assert state["_messages_applied"] == 2


def test_rebuild_book_returns_none_when_nothing_collected(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_book(database_path, [{"i": "HSBK.KZ", "n": 0}])

    assert rebuild_order_book(database_path, "KSPI.KZ") is None


def test_rebuild_book_applies_inserts_and_sorts_each_side(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [
            {
                "i": "HSBK.KZ",
                "n": 0,
                "ins": [
                    {"p": 385.0, "s": "S", "q": 10, "k": 0},
                    {"p": 384.5, "s": "S", "q": 20, "k": 1},
                    {"p": 384.0, "s": "B", "q": 30, "k": 2},
                    {"p": 383.5, "s": "B", "q": 40, "k": 3},
                ],
            }
        ],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert [level["p"] for level in book["asks"]] == [384.5, 385.0]
    assert [level["p"] for level in book["bids"]] == [384.0, 383.5]
    assert book["_from_snapshot"] is True


def test_rebuild_book_applies_updates_by_level_key(tmp_path: Path) -> None:
    """upd carries the same k as the level it modifies (F-40)."""
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [
            {"i": "HSBK.KZ", "n": 0, "ins": [{"p": 384.49, "s": "S", "q": 39, "k": 9}]},
            {"i": "HSBK.KZ", "n": 1, "upd": [{"p": 384.49, "s": "S", "q": 88, "k": 9}]},
            {"i": "HSBK.KZ", "n": 2, "upd": [{"p": 384.49, "s": "S", "q": 76, "k": 9}]},
        ],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert len(book["asks"]) == 1
    assert book["asks"][0]["q"] == 76


def test_rebuild_book_applies_deletes(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [
            {
                "i": "HSBK.KZ",
                "n": 0,
                "ins": [
                    {"p": 385.0, "s": "S", "q": 10, "k": 0},
                    {"p": 384.0, "s": "B", "q": 30, "k": 1},
                ],
            },
            {"i": "HSBK.KZ", "n": 1, "del": [{"p": 385.0, "k": 0}]},
        ],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert book["asks"] == []
    assert len(book["bids"]) == 1


def test_rebuild_book_restarts_from_the_latest_full_book(tmp_path: Path) -> None:
    """Levels from before a reconnect must not survive into the new book."""
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [
            {"i": "HSBK.KZ", "n": 0, "ins": [{"p": 999.0, "s": "S", "q": 1, "k": 0}]},
            {"i": "HSBK.KZ", "n": 1, "upd": [{"p": 999.0, "s": "S", "q": 2, "k": 0}]},
            {"i": "HSBK.KZ", "n": 0, "ins": [{"p": 385.0, "s": "S", "q": 10, "k": 0}]},
        ],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert [level["p"] for level in book["asks"]] == [385.0]
    assert book["_messages_applied"] == 1


def test_rebuild_book_reports_when_no_full_book_was_captured(tmp_path: Path) -> None:
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [{"i": "HSBK.KZ", "n": 7, "upd": [{"p": 384.0, "s": "B", "q": 5, "k": 3}]}],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert book["_from_snapshot"] is False


def test_rebuild_book_tolerates_missing_diff_arrays(tmp_path: Path) -> None:
    """Not every message carries all three of ins/del/upd."""
    database_path = tmp_path / "market.sqlite3"
    _store_book(
        database_path,
        [
            {"i": "HSBK.KZ", "n": 0, "ins": [{"p": 384.0, "s": "B", "q": 5, "k": 0}]},
            {"i": "HSBK.KZ", "n": 1},
        ],
    )

    book = rebuild_order_book(database_path, "HSBK.KZ")

    assert book is not None
    assert len(book["bids"]) == 1
