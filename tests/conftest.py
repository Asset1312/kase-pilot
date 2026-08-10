"""Shared test safeguards.

The collected market database lives inside the project tree, so a test that
forgets to redirect it writes into the developer's real, irreplaceable market
history. This happened once during development; the guard below makes it fail
loudly instead of silently corrupting collected data.

The check intercepts the store as it opens, rather than watching the file for
changes: a collector running in the background writes to that same file
continuously, so any file-watching check would fire on other people's writes
and not on the test's own.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from kase_pilot.core.config import market_database_path
from kase_pilot.storage._sqlite_store import SqliteStreamStore


@pytest.fixture(autouse=True)
def _protect_real_market_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Fail any test that opens a store on the real market database."""
    real_database = market_database_path().resolve()
    original_enter = SqliteStreamStore.__enter__

    def guarded_enter(self: SqliteStreamStore) -> SqliteStreamStore:
        if self._database_path.resolve() == real_database:
            raise AssertionError(
                f"Test opened the real market database at {real_database}. "
                "Pass project_root=tmp_path so collection is redirected."
            )
        return original_enter(self)

    monkeypatch.setattr(SqliteStreamStore, "__enter__", guarded_enter)
    yield
