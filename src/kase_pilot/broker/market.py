"""Market data service for the kase_pilot.broker package."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter
from kase_pilot.broker.models import JsonValue


class MarketService:
    """Retrieves market data from the broker API.

    Parameters
    ----------
    adapter:
        A fully constructed internal Tradernet SDK adapter.
    """

    def __init__(self, adapter: TradernetSdkAdapter) -> None:
        self._adapter = adapter

    def get_security_info(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, JsonValue]:
        """Return raw information for a broker instrument."""
        return self._adapter.get_security_info(ticker, sup=sup)

    def get_quotes(
        self,
        symbols: Sequence[str],
    ) -> dict[str, JsonValue]:
        """Return current quotes for broker instruments."""
        return self._adapter.get_quotes(symbols)

    def find_symbol(
        self,
        query: str,
    ) -> dict[str, JsonValue]:
        """Return broker instruments matching a search query."""
        return self._adapter.find_symbol(query)

    def get_news(
        self,
        query: str,
        symbol: str | None = None,
        story_id: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Return raw broker news."""
        return self._adapter.get_news(
            query,
            symbol=symbol,
            story_id=story_id,
            limit=limit,
        )

    def get_market_status(
        self,
        market: str = "*",
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Return raw market status information."""
        return self._adapter.get_market_status(market, mode=mode)

    def get_most_traded(
        self,
        instrument_type: str = "stocks",
        exchange: str = "usa",
        gainers: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return raw most-traded market data."""
        return self._adapter.get_most_traded(
            instrument_type,
            exchange=exchange,
            gainers=gainers,
            limit=limit,
        )

    def get_historical(
        self,
        start: datetime = datetime(2011, 1, 11),  # noqa: DTZ001
        end: datetime = datetime.now(),  # noqa: B008, DTZ005
    ) -> dict[str, Any]:
        """Return raw historical orders."""
        return self._adapter.get_historical(start, end)

    def get_candles(
        self,
        symbol: str,
        start: datetime = datetime(2010, 1, 1),  # noqa: DTZ001
        end: datetime = datetime.now(),  # noqa: B008, DTZ005
        timeframe: int = 86400,
    ) -> dict[str, JsonValue]:
        """Return historical candles for a broker instrument."""
        return self._adapter.get_candles(symbol, start, end, timeframe)

    def get_current_quotes(self) -> object:
        """Return current quotes.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError

    def get_historical_quotes(self) -> object:
        """Return historical quotes.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError
