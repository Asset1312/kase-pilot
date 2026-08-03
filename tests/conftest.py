"""Shared test safeguards.

The collected market database lives inside the project tree, so a test that
forgets to redirect it writes into the developer's real, irreplaceable market
history. This happened once during development; the guard below makes it fail
loudly instead of silently corrupting collected data.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from kase_pilot.core.config import market_database_path


@pytest.fixture(autouse=True)
def _protect_real_market_database() -> Iterator[None]:
    """Fail any test that writes to the real collected market database."""
    real_database = market_database_path()
    before = real_database.stat().st_mtime_ns if real_database.exists() else None

    yield

    after = real_database.stat().st_mtime_ns if real_database.exists() else None
    if before != after:
        raise AssertionError(
            f"Test modified the real market database at {real_database}. "
            "Pass project_root=tmp_path so collection is redirected."
        )
