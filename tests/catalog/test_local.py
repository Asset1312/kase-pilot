"""Tests for KASE Pilot's local instrument catalog."""

from __future__ import annotations

from typing import Any

from kase_pilot.catalog import LocalInstrumentCatalog


def _catalog_with(instruments: list[dict[str, Any]]) -> LocalInstrumentCatalog:
    catalog = LocalInstrumentCatalog()
    catalog._instruments = instruments
    catalog._by_ticker = {
        instrument["ticker"].casefold(): instrument for instrument in instruments
    }
    return catalog


def test_loads_bundled_resource_without_network() -> None:
    catalog = LocalInstrumentCatalog()

    assert isinstance(catalog._instruments, list)
    assert catalog._instruments


def test_bundled_seed_contains_curated_entries_by_ticker() -> None:
    catalog = LocalInstrumentCatalog()

    tickers = {instrument["ticker"] for instrument in catalog._instruments}

    assert {"HSBK.KZ", "AAPL.US"}.issubset(tickers)


def test_bundled_seed_entries_have_required_fields() -> None:
    catalog = LocalInstrumentCatalog()

    for instrument in catalog._instruments:
        assert isinstance(instrument["ticker"], str) and instrument["ticker"]
        assert isinstance(instrument["exchange"], str) and instrument["exchange"]


def test_get_returns_instrument_by_exact_ticker() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE"}
    catalog = _catalog_with([entry])

    assert catalog.get("HSBK.KZ") is entry


def test_get_ticker_lookup_is_case_insensitive() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE"}
    catalog = _catalog_with([entry])

    assert catalog.get("hsbk.kz") is entry
    assert catalog.get("Hsbk.Kz") is entry


def test_get_unknown_ticker_returns_none() -> None:
    catalog = _catalog_with([{"ticker": "HSBK.KZ", "exchange": "KASE"}])

    assert catalog.get("AAPL.US") is None


def test_find_matches_ticker_substring_case_insensitively() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE", "name": "Halyk Bank"}
    catalog = _catalog_with([entry])

    assert catalog.find("hsbk") == [entry]
    assert catalog.find("HSBK") == [entry]


def test_find_matches_name_substring_case_insensitively() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE", "name": "Halyk Bank"}
    catalog = _catalog_with([entry])

    assert catalog.find("halyk") == [entry]


def test_find_matches_isin_substring() -> None:
    entry = {
        "ticker": "HSBK.KZ",
        "exchange": "KASE",
        "name": "Halyk Bank",
        "isin": "KZ1C00003546",
    }
    catalog = _catalog_with([entry])

    assert catalog.find("kz1c00003546") == [entry]


def test_find_does_not_raise_when_name_or_isin_is_null() -> None:
    entry = {
        "ticker": "AAPL.US",
        "exchange": "usa",
        "name": None,
        "isin": None,
    }
    catalog = _catalog_with([entry])

    assert catalog.find("aapl") == [entry]
    assert catalog.find("nonexistent") == []


def test_find_no_match_returns_empty_list() -> None:
    catalog = _catalog_with(
        [{"ticker": "HSBK.KZ", "exchange": "KASE", "name": "Halyk Bank"}]
    )

    assert catalog.find("nonexistent") == []


def test_get_symbols_without_exchange_returns_all_entries() -> None:
    instruments = [
        {"ticker": "HSBK.KZ", "exchange": "KASE"},
        {"ticker": "AAPL.US", "exchange": "usa"},
    ]
    catalog = _catalog_with(instruments)

    result = catalog.get_symbols()

    assert result == {"exchange": None, "symbols": instruments}


def test_get_symbols_filters_by_exchange() -> None:
    kase_entry = {"ticker": "HSBK.KZ", "exchange": "KASE"}
    other_entry = {"ticker": "AAPL.US", "exchange": "usa"}
    catalog = _catalog_with([kase_entry, other_entry])

    result = catalog.get_symbols("KASE")

    assert result == {"exchange": "KASE", "symbols": [kase_entry]}


def test_get_symbols_exchange_filter_is_case_insensitive() -> None:
    kase_entry = {"ticker": "HSBK.KZ", "exchange": "KASE"}
    catalog = _catalog_with([kase_entry])

    assert catalog.get_symbols("kase") == {"exchange": "kase", "symbols": [kase_entry]}
    assert catalog.get_symbols("KaSe") == {"exchange": "KaSe", "symbols": [kase_entry]}


def test_get_symbols_unknown_exchange_returns_empty_list() -> None:
    catalog = _catalog_with([{"ticker": "HSBK.KZ", "exchange": "KASE"}])

    result = catalog.get_symbols("NASDAQ")

    assert result == {"exchange": "NASDAQ", "symbols": []}


def test_get_all_filters_by_market_and_excludes_expired_by_default() -> None:
    active = {
        "ticker": "HSBK.KZ",
        "exchange": "KASE",
        "market": "KASE_STOCK",
        "expired": False,
    }
    expired = {
        "ticker": "OLD.KZ",
        "exchange": "KASE",
        "market": "KASE_STOCK",
        "expired": True,
    }
    other_market = {
        "ticker": "AAPL.US",
        "exchange": "usa",
        "market": "US_STOCK",
        "expired": False,
    }
    catalog = _catalog_with([active, expired, other_market])

    result = catalog.get_all("KASE_STOCK")

    assert result == [active]


def test_get_all_market_filter_is_case_insensitive() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE", "market": "KASE_STOCK"}
    catalog = _catalog_with([entry])

    assert catalog.get_all("kase_stock") == [entry]
    assert catalog.get_all("Kase_Stock") == [entry]


def test_get_all_unknown_market_returns_empty_list() -> None:
    catalog = _catalog_with(
        [{"ticker": "HSBK.KZ", "exchange": "KASE", "market": "KASE_STOCK"}]
    )

    assert catalog.get_all("NO_SUCH_MARKET") == []


def test_get_all_null_market_never_matches() -> None:
    catalog = _catalog_with([{"ticker": "AAPL.US", "exchange": "usa", "market": None}])

    assert catalog.get_all("usa") == []
    assert catalog.get_all("") == []


def test_get_all_includes_expired_when_requested() -> None:
    active = {
        "ticker": "HSBK.KZ",
        "exchange": "KASE",
        "market": "KASE_STOCK",
        "expired": False,
    }
    expired = {
        "ticker": "OLD.KZ",
        "exchange": "KASE",
        "market": "KASE_STOCK",
        "expired": True,
    }
    catalog = _catalog_with([active, expired])

    result = catalog.get_all("KASE_STOCK", show_expired=True)

    assert result == [active, expired]


def test_get_all_treats_missing_expired_field_as_not_expired() -> None:
    entry = {"ticker": "HSBK.KZ", "exchange": "KASE", "market": "KASE_STOCK"}
    catalog = _catalog_with([entry])

    assert catalog.get_all("KASE_STOCK") == [entry]
