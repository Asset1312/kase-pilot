"""Base interface for stream storage backends."""

from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType
from typing import Any, Protocol, Self


class StreamBackend(Protocol):
    """Protocol defining the required methods for a stream storage backend."""

    def open_session(self, symbols: tuple[str, ...]) -> Self:
        """Record what this collector run covers, before entering it."""
        ...

    def __enter__(self) -> Self:
        """Open the backend connection and initialize the session."""
        ...

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the session and connection."""
        ...

    def save(self, message: Mapping[str, Any]) -> None:
        """Append one raw stream message verbatim."""
        ...

    def record_interruption(self, attempt: int) -> None:
        """Record that the connection dropped and a retry is pending."""
        ...

    def record_resumption(self) -> None:
        """Close out the open interruption for this session, if any."""
        ...
