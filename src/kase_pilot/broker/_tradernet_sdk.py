"""Internal adapter for the officially linked Tradernet SDK."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, cast

from tradernet import Tradernet

from kase_pilot.broker.models import JsonValue
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


class TradernetSdkAdapter:
    """Expose confirmed broker operations through the SDK."""

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

    def user_info(self) -> dict[str, JsonValue]:
        """Return user information without transforming the SDK response."""
        try:
            response: Any = self._client.user_info()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping user information response"
            )

        return cast(dict[str, JsonValue], response)

    def account_summary(self) -> dict[str, JsonValue]:
        """Return an account summary without transforming the SDK response."""
        try:
            response: Any = self._client.account_summary()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping account summary response"
            )

        return cast(dict[str, JsonValue], response)

    def get_placed(
        self,
        active: bool = True,
    ) -> dict[str, JsonValue]:
        """Return placed orders without transforming the SDK response."""
        try:
            response: Any = self._client.get_placed(active=active)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping placed orders response"
            )

        return cast(dict[str, JsonValue], response)

    def get_trades_history(
        self,
        start: date,
        end: date,
        symbol: str | None = None,
        limit: int | None = None,
    ) -> dict[str, JsonValue]:
        """Return trades history without transforming the SDK response."""
        kwargs: dict[str, object] = {}
        if symbol is not None:
            kwargs["symbol"] = symbol
        if limit is not None:
            kwargs["limit"] = limit

        try:
            response: Any = self._client.get_trades_history(
                start,
                end,
                **kwargs,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        if not isinstance(response, Mapping):
            raise ValidationError(
                "Tradernet SDK returned a non-mapping trades history response"
            )

        return cast(dict[str, JsonValue], response)
