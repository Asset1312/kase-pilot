"""KASE Pilot's own bundled instrument catalog.

The previous ``symbols``/``instruments`` commands depended on
``Tradernet.symbols()`` (-> ``authorized_request("getReadyList")``) and
``Tradernet.get_all()`` (-> ``/refbooks/<date>/<market>.json.zip``). Both are
confirmed to return HTTP 404 with no known replacement (see
``docs/API_NOTES.md``). This module replaces that dependency entirely: it
reads a static, project-bundled JSON resource and never makes a network call.

The data format is defined by KASE Pilot itself and intentionally does not
mirror any unconfirmed Tradernet/Freedom response shape. It distinguishes
two separate concepts that the original Tradernet-backed calls conflated:

- ``exchange`` — the broad exchange code, matched by ``symbols --exchange``.
- ``market`` — the finer-grained reference-book code (e.g. the
  ``KASE_STOCK``-style refbook name), matched by ``instruments --market``.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

_DATA_PACKAGE = "kase_pilot.catalog.data"
_DATA_FILE = "instruments.json"


def _load_instruments() -> list[dict[str, Any]]:
    text = (
        resources.files(_DATA_PACKAGE).joinpath(_DATA_FILE).read_text(encoding="utf-8")
    )
    payload: Any = json.loads(text)
    return payload["instruments"]


def _matches(value: Any, query: str) -> bool:
    return isinstance(value, str) and value.casefold() == query.casefold()


class LocalInstrumentCatalog:
    """Read-only, project-bundled instrument reference data.

    The backing file (``catalog/data/instruments.json``) is a versioned
    envelope; see ``catalog/data/README.md`` for the full format
    description. Each entry under ``instruments`` has required ``ticker``
    and ``exchange`` keys, plus optional ``market``, ``name``, ``currency``,
    and ``expired`` fields (``null``/absent when not confirmed). The schema
    is owned by KASE Pilot and does not mirror any Tradernet/Freedom
    response shape.
    """

    def __init__(self) -> None:
        self._instruments = _load_instruments()

        self._by_ticker = {
            instrument["ticker"].casefold(): instrument
            for instrument in self._instruments
        }

    def get(self, ticker: str) -> dict[str, Any] | None:
        """Return one instrument by ticker.

        Matching is case-insensitive. Returns ``None`` if the ticker is not
        present in the catalog.
        """
        return self._by_ticker.get(ticker.casefold())

    def find(self, query: str) -> list[dict[str, Any]]:
        """Return catalog instruments matching a search query.

        Search is case-insensitive and matches ticker, instrument name,
        and ISIN by substring. A ``null`` field never matches.
        """
        query = query.casefold()

        return [
            instrument
            for instrument in self._instruments
            if (
                query in instrument["ticker"].casefold()
                or query in (instrument.get("name") or "").casefold()
                or query in (instrument.get("isin") or "").casefold()
            )
        ]

    def get_symbols(self, exchange: str | None = None) -> dict[str, Any]:
        """Return catalog symbols, optionally filtered by exchange.

        Matching is case-insensitive. An exchange value with no matching
        entries returns an empty ``symbols`` list rather than raising.
        """
        if exchange is None:
            matches = list(self._instruments)
        else:
            matches = [
                instrument
                for instrument in self._instruments
                if _matches(instrument.get("exchange"), exchange)
            ]
        return {"exchange": exchange, "symbols": matches}

    def get_all(
        self,
        market: str,
        show_expired: bool = False,
    ) -> list[dict[str, Any]]:
        """Return catalog instruments for one market (refbook-style code).

        Matching is case-insensitive. A market value with no matching
        entries returns an empty list rather than raising. Entries with no
        confirmed ``market`` value never match any query.
        """
        matches = [
            instrument
            for instrument in self._instruments
            if _matches(instrument.get("market"), market)
        ]
        if not show_expired:
            matches = [
                instrument
                for instrument in matches
                if not instrument.get("expired", False)
            ]
        return matches
