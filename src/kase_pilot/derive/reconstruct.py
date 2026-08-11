"""Rebuild point-in-time state from the raw stream log.

Nothing here is authoritative: it is one interpretation of the raw messages,
kept deliberately separate from storage so it can be rewritten and re-run
whenever understanding of the protocol improves (see docs/API_NOTES.md
F-27/F-28/F-38/F-40). The raw log remains the source of truth.

Two reconstructions are provided, mirroring the two streams:

- ``rebuild_quote`` merges quote deltas onto the most recent snapshot.
- ``rebuild_order_book`` replays positional ``ins``/``del``/``upd`` diffs.

Both deliberately order messages by their stored ``id`` (insertion order)
rather than the broker's own ``n`` counter, because whether ``n`` resets per
connection, per trading day, or never is not established (F-40).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

# Marks a message that carries a complete picture rather than a delta.
# Observed, not documented — see F-38 (quotes) and F-40 (order book).
_QUOTE_SNAPSHOT_FIELD = "init"
_BOOK_SEQUENCE_FIELD = "n"


def _read_messages(
    database_path: Path,
    table: str,
    ticker: str,
) -> list[dict[str, Any]]:
    connection = sqlite3.connect(database_path)
    try:
        # Table name is a module constant, never user input; values are bound.
        rows = connection.execute(
            f"SELECT payload FROM {table} WHERE ticker = ? ORDER BY id",
            (ticker,),
        ).fetchall()
    finally:
        connection.close()
    return [json.loads(payload) for (payload,) in rows]


def rebuild_quote(database_path: Path, ticker: str) -> dict[str, Any] | None:
    """Merge stored quote deltas into the latest known state for one ticker.

    Returns ``None`` when nothing was ever recorded for the ticker.

    Merging starts from the most recent snapshot (``init: 1``) so that stale
    fields from before a reconnect cannot leak into the result. If no snapshot
    was ever stored, every message is merged in order and the result is
    necessarily incomplete — which is reported through ``_from_snapshot``.
    """
    messages = _read_messages(database_path, "quote_messages", ticker)
    if not messages:
        return None

    start = 0
    from_snapshot = False
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get(_QUOTE_SNAPSHOT_FIELD) == 1:
            start = index
            from_snapshot = True
            break

    state: dict[str, Any] = {}
    for message in messages[start:]:
        state.update(message)

    state["_from_snapshot"] = from_snapshot
    state["_messages_applied"] = len(messages) - start
    return state


def rebuild_order_book(database_path: Path, ticker: str) -> dict[str, Any] | None:
    """Replay stored order-book diffs into a current book for one ticker.

    Returns ``None`` when nothing was ever recorded for the ticker.

    Replay starts at the most recent full book (``n: 0``). ``k`` is the current
    positional index in the broker's ordered level list, so every operation is
    applied sequentially to the list produced by earlier operations. Bids and
    asks are separated by the ``s`` field and returned sorted by price — bids
    descending, asks ascending — so the top of book is first in each list.
    Derived level ``k`` values are reindexed to their current positions; stored
    raw messages remain untouched.
    """
    messages = _read_messages(database_path, "order_book_messages", ticker)
    if not messages:
        return None

    start = 0
    from_snapshot = False
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].get(_BOOK_SEQUENCE_FIELD) == 0:
            start = index
            from_snapshot = True
            break

    levels: list[dict[str, Any]] = []
    for message in messages[start:]:
        for level in message.get("del") or []:
            position = _book_position(level, "del", len(levels))
            levels.pop(position)
        for level in message.get("ins") or []:
            position = _book_position(level, "ins", len(levels), allow_append=True)
            levels.insert(position, dict(level))
        for level in message.get("upd") or []:
            position = _book_position(level, "upd", len(levels))
            levels[position].update(level)
        _reindex_levels(levels)

    bids = [level for level in levels if level.get("s") == "B"]
    asks = [level for level in levels if level.get("s") == "S"]
    bids.sort(key=lambda level: level.get("p", 0), reverse=True)
    asks.sort(key=lambda level: level.get("p", 0))

    return {
        "ticker": ticker,
        "bids": bids,
        "asks": asks,
        "_from_snapshot": from_snapshot,
        "_messages_applied": len(messages) - start,
    }


def _book_position(
    level: Any,
    operation: str,
    book_size: int,
    *,
    allow_append: bool = False,
) -> int:
    if not isinstance(level, dict):
        raise TypeError(f"order-book {operation} entry must be an object")
    position = level.get("k")
    if isinstance(position, bool) or not isinstance(position, int):
        raise TypeError(f"order-book {operation} index must be an integer")
    if position < 0:
        raise ValueError(f"order-book {operation} index must be non-negative")
    if not allow_append and position >= book_size:
        raise ValueError(
            f"order-book {operation} index {position} out of range "
            f"for book size {book_size}"
        )
    return position


def _reindex_levels(levels: list[dict[str, Any]]) -> None:
    for position, level in enumerate(levels):
        level["k"] = position
