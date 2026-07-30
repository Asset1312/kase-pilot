"""Internal adapter for the officially linked Tradernet SDK."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime, time
from typing import Any, cast

from tradernet import Tradernet

from kase_pilot.broker.models import JsonValue
from kase_pilot.core.exceptions import ApiRequestError, ValidationError


def _require_mapping(response: object, response_name: str) -> Mapping[str, Any]:
    if not isinstance(response, Mapping):
        raise ValidationError(
            f"Tradernet SDK returned a non-mapping {response_name} response"
        )
    return response


def _require_list(response: object, response_name: str) -> list[Any]:
    if not isinstance(response, list):
        raise ValidationError(
            f"Tradernet SDK returned a non-list {response_name} response"
        )
    return response


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

        return cast(
            dict[str, JsonValue],
            dict(_require_mapping(response, "security information")),
        )

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

    def get_symbols(
        self,
        exchange: str | None = None,
    ) -> dict[str, Any]:
        """Return symbol lists without transforming the SDK response."""
        try:
            if exchange is None:
                response: Any = self._client.symbols()
            else:
                response = self._client.symbols(exchange)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "symbols"))

    def get_symbol(
        self,
        symbol: str,
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Return symbol information without transforming the SDK response."""
        try:
            if lang is None:
                response: Any = self._client.symbol(symbol)
            else:
                response = self._client.symbol(symbol, lang)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "symbol"))

    def export_securities(
        self,
        symbols: Sequence[str],
        fields: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Export securities without transforming the SDK response."""
        try:
            if fields is None:
                response: Any = self._client.export_securities(symbols)
            else:
                response = self._client.export_securities(symbols, fields)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            list[dict[str, Any]],
            _require_list(response, "securities export"),
        )

    def get_options(
        self,
        underlying: str,
        exchange: str,
    ) -> list[dict[str, Any]]:
        """Return options without transforming the SDK response."""
        try:
            response: Any = self._client.get_options(underlying, exchange)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(list[dict[str, Any]], _require_list(response, "options"))

    def get_tariffs(self) -> dict[str, Any]:
        """Return tariffs without transforming the SDK response."""
        try:
            response: Any = self._client.get_tariffs_list()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "tariffs"))

    def list_security_sessions(self) -> dict[str, Any]:
        """Return security sessions without transforming the SDK response."""
        try:
            response: Any = self._client.list_security_sessions()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, Any],
            _require_mapping(response, "security sessions"),
        )

    def get_order_files(
        self,
        order_id: int | None,
        internal_id: int | None,
    ) -> dict[str, Any]:
        """Return order files without transforming the SDK response."""
        try:
            response: Any = self._client.get_order_files(order_id, internal_id)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "order files"))

    def get_user_data(self) -> dict[str, Any]:
        """Return user data without transforming the SDK response."""
        try:
            response: Any = self._client.get_user_data()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "user data"))

    def check_missing_fields(
        self,
        step: int,
        office: str,
    ) -> dict[str, Any]:
        """Return missing profile fields without transforming the SDK response."""
        try:
            response: Any = self._client.check_missing_fields(step, office)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, Any],
            _require_mapping(response, "missing fields"),
        )

    def get_news(
        self,
        query: str,
        symbol: str | None = None,
        story_id: str | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        """Return news without transforming the SDK response."""
        try:
            response: Any = self._client.get_news(
                query,
                symbol=symbol,
                story_id=story_id,
                limit=limit,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "news"))

    def get_market_status(
        self,
        market: str = "*",
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Return market status without transforming the SDK response."""
        try:
            response: Any = self._client.get_market_status(market, mode=mode)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "market status"))

    def get_most_traded(
        self,
        instrument_type: str = "stocks",
        exchange: str = "usa",
        gainers: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Return most-traded instruments without transforming the SDK response."""
        try:
            response: Any = self._client.get_most_traded(
                instrument_type,
                exchange=exchange,
                gainers=gainers,
                limit=limit,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "most-traded"))

    def get_historical(
        self,
        start: datetime = datetime(2011, 1, 11),  # noqa: DTZ001
        end: datetime = datetime.now(),  # noqa: B008, DTZ005
    ) -> dict[str, Any]:
        """Return historical orders without transforming the SDK response."""
        try:
            response: Any = self._client.get_historical(start, end)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "historical orders"))

    def corporate_actions(
        self,
        reception: int = 35,
    ) -> list[dict[str, Any]]:
        """Return planned corporate actions without transforming the SDK response."""
        try:
            response: Any = self._client.corporate_actions(reception)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            list[dict[str, Any]],
            _require_list(response, "corporate actions"),
        )

    def get_price_alerts(
        self,
        symbol: str | None = None,
    ) -> dict[str, Any]:
        """Return price alerts without transforming the SDK response."""
        try:
            response: Any = self._client.get_price_alerts(symbol)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "price alerts"))

    def get_requests_history(
        self,
        doc_id: int | None = None,
        exec_id: int | None = None,
        start: date = datetime(2011, 1, 11),  # noqa: DTZ001
        end: date = datetime.now(),  # noqa: B008, DTZ005
        limit: int | None = None,
        offset: int | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """Return client requests history without transforming the SDK response."""
        try:
            response: Any = self._client.get_requests_history(
                doc_id,
                exec_id,
                start,
                end,
                limit,
                offset,
                status,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, Any],
            _require_mapping(response, "requests history"),
        )

    def get_broker_report(
        self,
        start: str | date = date(1970, 1, 1),
        end: str | date = date.today(),  # noqa: B008, DTZ011
        period: time = time(23, 59, 59),
    ) -> dict[str, Any]:
        """Return a broker report without transforming the SDK response."""
        try:
            response: Any = self._client.get_broker_report(
                start=start,
                end=end,
                period=period,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(dict[str, Any], _require_mapping(response, "broker report"))

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

        return cast(
            dict[str, JsonValue],
            _require_mapping(response, "user information"),
        )

    def account_summary(self) -> dict[str, JsonValue]:
        """Return an account summary without transforming the SDK response."""
        try:
            response: Any = self._client.account_summary()
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, JsonValue],
            _require_mapping(response, "account summary"),
        )

    def get_placed(
        self,
        active: bool = True,
    ) -> dict[str, JsonValue]:
        """Return placed orders without transforming the SDK response."""
        try:
            response: Any = self._client.get_placed(active=active)
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, JsonValue],
            _require_mapping(response, "placed orders"),
        )

    def get_trades_history(
        self,
        start: date,
        end: date,
        symbol: str | None = None,
        limit: int | None = None,
        currency: str | None = None,
    ) -> dict[str, JsonValue]:
        """Return trades history without transforming the SDK response."""
        kwargs: dict[str, object] = {}
        if symbol is not None:
            kwargs["symbol"] = symbol
        if limit is not None:
            kwargs["limit"] = limit
        if currency is not None:
            kwargs["currency"] = currency

        try:
            response: Any = self._client.get_trades_history(
                start,
                end,
                **kwargs,
            )
        except Exception as exc:
            raise ApiRequestError("Tradernet SDK request failed") from exc

        return cast(
            dict[str, JsonValue],
            _require_mapping(response, "trades history"),
        )
