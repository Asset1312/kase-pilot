"""Internal adapter for the officially linked Tradernet SDK."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast

from tradernet import Tradernet

from kase_pilot.broker.models import JsonValue
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class TradernetSdkAdapter:
    """Expose confirmed market-data operations through the SDK."""

    def __init__(self, client: Tradernet) -> None:
        self._client = client

    def get_security_info(
        self,
        ticker: str,
        *,
        sup: bool = True,
    ) -> dict[str, JsonValue]:
        try:
            response: Any = self._client.security_info(ticker, sup=sup)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping security information response"
            )

        return cast(dict[str, JsonValue], dict(response))

    def get_quotes(
        self,
        symbols: Sequence[str],
    ) -> dict[str, JsonValue]:
        """Return current quotes without transforming the SDK response."""
        try:
            return cast(dict[str, JsonValue], self._client.get_quotes(symbols))
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

    def find_symbol(
        self,
        query: str,
    ) -> dict[str, JsonValue]:
        """Return matching instruments without transforming the SDK response."""
        try:
            return cast(dict[str, JsonValue], self._client.find_symbol(query))
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

    def get_candles(
        self,
        symbol: str,
        start: datetime = datetime(2010, 1, 1),  # noqa: DTZ001
        end: datetime = datetime.now(),  # noqa: B008, DTZ005
        timeframe: int = 86400,
    ) -> dict[str, JsonValue]:
        """Return historical candles without transforming the SDK response."""
        try:
            return cast(
                dict[str, JsonValue],
                self._client.get_candles(symbol, start, end, timeframe),
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc
