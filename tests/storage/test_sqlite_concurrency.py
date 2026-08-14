"""Multi-process locking tests for the append-only SQLite collector store."""

from __future__ import annotations

import json
import multiprocessing
import queue
import sqlite3
from pathlib import Path
from typing import Any

import pytest

import kase_pilot.storage._sqlite_store as sqlite_store_module
from kase_pilot.storage._sqlite_store import (
    SQLITE_BUSY_TIMEOUT_MS,
    SqliteStreamStore,
)

_WRITER_COUNT = 5
_MESSAGES_PER_WRITER = 300


def _store(database_path: Path, writer_id: int) -> SqliteStreamStore:
    is_quote_writer = writer_id == 0
    return SqliteStreamStore(
        database_path=database_path,
        table="quote_messages" if is_quote_writer else "order_book_messages",
        ticker_field="c" if is_quote_writer else "i",
        stream="quotes" if is_quote_writer else "orderbook",
    )


def _writer_process(
    database_path: str,
    writer_id: int,
    message_count: int,
    start_event: Any,
    result_queue: Any,
) -> None:
    """Independent process target matching the production collector topology."""
    start_event.wait()
    try:
        symbol = "QUOTES.KZ" if writer_id == 0 else f"BOOK{writer_id}.KZ"
        with _store(Path(database_path), writer_id).open_session((symbol,)) as store:
            for sequence in range(message_count):
                message_id = f"{writer_id}:{sequence}"
                message = {
                    "c" if writer_id == 0 else "i": symbol,
                    "message_id": message_id,
                    "sequence": sequence,
                    "writer_id": writer_id,
                }
                store.save(message)
                if writer_id == 0 and sequence == message_count // 2:
                    store.record_interruption(1)
                    store.record_resumption()
        result_queue.put((writer_id, None))
    except Exception as error:  # noqa: BLE001 - returned to parent assertion
        result_queue.put((writer_id, f"{type(error).__name__}: {error}"))


def _run_writers(
    database_path: Path,
    *,
    writer_count: int = _WRITER_COUNT,
    message_count: int = _MESSAGES_PER_WRITER,
) -> list[str]:
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    result_queue = context.Queue()
    processes = [
        context.Process(
            target=_writer_process,
            args=(
                str(database_path),
                writer_id,
                message_count,
                start_event,
                result_queue,
            ),
        )
        for writer_id in range(writer_count)
    ]
    for process in processes:
        process.start()
    start_event.set()
    for process in processes:
        process.join(timeout=90)
    errors = [
        f"process {index} did not terminate"
        for index, process in enumerate(processes)
        if process.is_alive()
    ]
    for process in processes:
        if process.is_alive():
            process.terminate()
            process.join(timeout=10)
        elif process.exitcode != 0:
            errors.append(f"process {process.pid} exited with {process.exitcode}")
    for _ in processes:
        try:
            writer_id, error = result_queue.get(timeout=5)
        except queue.Empty:
            errors.append("writer process returned no result")
            continue
        if error is not None:
            errors.append(f"writer {writer_id}: {error}")
    result_queue.close()
    result_queue.join_thread()
    return errors


def _payloads(connection: sqlite3.Connection) -> list[dict[str, object]]:
    rows = connection.execute(
        "SELECT payload FROM quote_messages "
        "UNION ALL SELECT payload FROM order_book_messages"
    )
    return [json.loads(payload) for (payload,) in rows]


def test_connection_enables_wal_busy_timeout_and_normal_sync(tmp_path: Path) -> None:
    database_path = tmp_path / "settings.sqlite3"

    with _store(database_path, 0).open_session(("QUOTES.KZ",)) as store:
        connection = store._connection
        assert connection is not None
        ((journal_mode,),) = connection.execute("PRAGMA journal_mode").fetchall()
        ((busy_timeout,),) = connection.execute("PRAGMA busy_timeout").fetchall()
        ((synchronous,),) = connection.execute("PRAGMA synchronous").fetchall()

    assert str(journal_mode).lower() == "wal"
    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MS
    assert synchronous == 1  # SQLite's numeric value for NORMAL.


def test_connect_uses_timeout_derived_from_busy_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "connect-timeout.sqlite3"
    original_connect = sqlite_store_module.sqlite3.connect
    captured_timeout: float | None = None

    def connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        nonlocal captured_timeout
        captured_timeout = float(kwargs["timeout"])
        return original_connect(*args, **kwargs)

    monkeypatch.setattr(sqlite_store_module.sqlite3, "connect", connect)

    with _store(database_path, 0).open_session(("QUOTES.KZ",)):
        pass

    assert captured_timeout == SQLITE_BUSY_TIMEOUT_MS / 1_000


def test_concurrent_startup_initializes_schema_and_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "concurrent-startup.sqlite3"

    errors = _run_writers(database_path, message_count=0)

    assert errors == []
    connection = sqlite3.connect(database_path)
    try:
        ((session_count,),) = connection.execute(
            "SELECT COUNT(*) FROM collector_sessions"
        )
        ((open_sessions,),) = connection.execute(
            "SELECT COUNT(*) FROM collector_sessions WHERE finished_at IS NULL"
        )
        tables = {
            name
            for (name,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()

    assert session_count == _WRITER_COUNT
    assert open_sessions == 0
    assert {
        "collector_sessions",
        "quote_messages",
        "order_book_messages",
        "collector_interruptions",
    }.issubset(tables)


def test_five_process_stress_preserves_every_message_and_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "five-writer-stress.sqlite3"
    attempted = _WRITER_COUNT * _MESSAGES_PER_WRITER

    errors = _run_writers(database_path)

    connection = sqlite3.connect(database_path)
    try:
        payloads = _payloads(connection)
        message_ids = [str(payload["message_id"]) for payload in payloads]
        ((quote_count,),) = connection.execute("SELECT COUNT(*) FROM quote_messages")
        ((book_count,),) = connection.execute(
            "SELECT COUNT(*) FROM order_book_messages"
        )
        sessions = list(
            connection.execute(
                "SELECT stream, symbols, started_at, finished_at "
                "FROM collector_sessions ORDER BY id"
            )
        )
        interruptions = list(
            connection.execute(
                "SELECT attempt, failed_at, resumed_at FROM collector_interruptions"
            )
        )
        ((journal_mode,),) = connection.execute("PRAGMA journal_mode").fetchall()
        ((quick_check,),) = connection.execute("PRAGMA quick_check").fetchall()
        ((integrity_check,),) = connection.execute("PRAGMA integrity_check").fetchall()
    finally:
        connection.close()

    duplicate_count = len(message_ids) - len(set(message_ids))
    operational_error_count = sum("OperationalError" in error for error in errors)
    metrics = {
        "attempted_writes": attempted,
        "successful_rows": len(payloads),
        "duplicate_count": duplicate_count,
        "operational_error_count": operational_error_count,
        "journal_mode": str(journal_mode).lower(),
        "quick_check": quick_check,
        "integrity_check": integrity_check,
    }
    print(f"SQLITE_STRESS_METRICS={json.dumps(metrics, sort_keys=True)}")

    assert errors == []
    assert quote_count == _MESSAGES_PER_WRITER
    assert book_count == (_WRITER_COUNT - 1) * _MESSAGES_PER_WRITER
    assert len(payloads) == attempted
    assert duplicate_count == 0
    assert len(sessions) == _WRITER_COUNT
    assert all(started_at and finished_at for _, _, started_at, finished_at in sessions)
    assert [stream for stream, *_ in sessions].count("quotes") == 1
    assert [stream for stream, *_ in sessions].count("orderbook") == 4
    assert all(json.loads(symbols) for _, symbols, *_ in sessions)
    assert len(interruptions) == 1
    assert interruptions[0][0] == 1
    assert interruptions[0][1]
    assert interruptions[0][2]
    assert str(journal_mode).lower() == "wal"
    assert quick_check == "ok"
    assert integrity_check == "ok"


class _BusyOnceConnection:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self.busy_raised = False

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
        if sql.startswith("INSERT INTO quote_messages") and not self.busy_raised:
            self.busy_raised = True
            error = sqlite3.OperationalError("database is locked")
            error.sqlite_errorcode = sqlite3.SQLITE_BUSY
            raise error
        return self._connection.execute(sql, parameters)

    def __getattr__(self, name: str) -> object:
        return getattr(self._connection, name)


def test_busy_retry_inserts_exactly_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    database_path = tmp_path / "retry.sqlite3"
    original_connect = sqlite_store_module.sqlite3.connect
    proxy: _BusyOnceConnection | None = None

    def connect(*args: object, **kwargs: object) -> _BusyOnceConnection:
        nonlocal proxy
        proxy = _BusyOnceConnection(original_connect(*args, **kwargs))
        return proxy

    monkeypatch.setattr(sqlite_store_module.sqlite3, "connect", connect)
    monkeypatch.setattr(sqlite_store_module.time, "sleep", lambda _: None)

    with _store(database_path, 0).open_session(("QUOTES.KZ",)) as store:
        store.save({"c": "QUOTES.KZ", "message_id": "only-once"})

    assert proxy is not None and proxy.busy_raised
    connection = original_connect(database_path)
    try:
        ((row_count,),) = connection.execute("SELECT COUNT(*) FROM quote_messages")
        ((distinct_payloads,),) = connection.execute(
            "SELECT COUNT(DISTINCT payload) FROM quote_messages"
        )
    finally:
        connection.close()

    assert row_count == 1
    assert distinct_payloads == 1


def test_non_lock_operational_error_is_not_retried(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "non-lock-error.sqlite3")
    attempts = 0

    def fail() -> None:
        nonlocal attempts
        attempts += 1
        error = sqlite3.OperationalError("database disk image is malformed")
        error.sqlite_errorcode = sqlite3.SQLITE_CORRUPT
        raise error

    try:
        with pytest.raises(sqlite3.OperationalError, match="malformed"):
            SqliteStreamStore._retry_locked(fail, connection)
    finally:
        connection.close()

    assert attempts == 1


def test_exit_commits_session_finish_and_closes_connection(tmp_path: Path) -> None:
    database_path = tmp_path / "clean-exit.sqlite3"
    store = _store(database_path, 0).open_session(("QUOTES.KZ",))

    with store:
        connection = store._connection
        assert connection is not None

    assert store._connection is None
    assert store._session_id is None
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        connection.execute("SELECT 1")
    verification = sqlite3.connect(database_path)
    try:
        ((finished_at,),) = verification.execute(
            "SELECT finished_at FROM collector_sessions"
        )
    finally:
        verification.close()
    assert finished_at
