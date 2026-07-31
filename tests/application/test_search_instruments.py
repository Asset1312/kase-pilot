"""Tests for the instrument search application use case."""

from __future__ import annotations

from typing import Any

from kase_pilot.application import SearchInstruments


class FakeCatalog:
    def __init__(self, response: list[dict[str, Any]]) -> None:
        self.response = response
        self.calls: list[object] = []

    def find(self, query: object) -> list[dict[str, Any]]:
        self.calls.append(query)
        return self.response


def test_execute_delegates_and_preserves_response_identity() -> None:
    query = "halyk"
    response = [{"ticker": "HSBK.KZ", "exchange": "KASE", "name": "Halyk Bank"}]
    catalog = FakeCatalog(response)
    use_case = SearchInstruments(catalog)  # type: ignore[arg-type]

    result = use_case.execute(query)

    assert catalog.calls == [query]
    assert catalog.calls[0] is query
    assert result is response


def test_execute_returns_empty_list_when_catalog_finds_nothing() -> None:
    catalog = FakeCatalog([])
    use_case = SearchInstruments(catalog)  # type: ignore[arg-type]

    assert use_case.execute("nonexistent") == []


def test_search_instruments_is_public_application_export() -> None:
    from kase_pilot import application

    assert application.SearchInstruments is SearchInstruments
