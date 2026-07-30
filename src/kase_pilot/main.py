"""Application entry point."""

import json
import math
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from datetime import time as datetime_time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from kase_pilot.app import (
    create_find_instrument,
    create_get_account_summary,
    create_get_broker_report,
    create_get_corporate_actions,
    create_get_current_quotes,
    create_get_historical,
    create_get_historical_candles,
    create_get_market_status,
    create_get_most_traded,
    create_get_news,
    create_get_placed_orders,
    create_get_price_alerts,
    create_get_requests_history,
    create_get_security_info,
    create_get_symbols,
    create_get_trades_history,
    create_get_user_info,
)
from kase_pilot.core.config import load_settings
from kase_pilot.core.exceptions import ConfigurationError
from kase_pilot.core.version import __version__

_USAGE = (
    "Usage:\n"
    "  kase-pilot info TICKER\n"
    "  kase-pilot quotes TICKER\n"
    "  kase-pilot search QUERY\n"
    "  kase-pilot symbols [--exchange EXCHANGE] [--json]\n"
    "  kase-pilot news QUERY [--symbol SYMBOL] [--story-id STORY_ID] "
    "[--limit LIMIT] [--json]\n"
    "  kase-pilot market-status [--market MARKET] [--mode MODE] [--json]\n"
    "  kase-pilot top [--type TYPE] [--exchange EXCHANGE] [--limit LIMIT] "
    "[--losers] [--json]\n"
    "  kase-pilot orders-history [--start DATETIME] [--end DATETIME] [--json]\n"
    "  kase-pilot corporate-actions [--reception DAYS] [--json]\n"
    "  kase-pilot price-alerts [--symbol SYMBOL] [--json]\n"
    "  kase-pilot requests-history [--doc-id ID] [--exec-id ID] "
    "[--start DATE] [--end DATE] [--limit LIMIT] [--offset OFFSET] "
    "[--status STATUS] [--json]\n"
    "  kase-pilot broker-report [--start DATE] [--end DATE] [--period TIME] "
    "[--json]\n"
    "  kase-pilot user\n"
    "  kase-pilot summary\n"
    "  kase-pilot portfolio [--symbol SYMBOL] "
    "[--sort ticker|value|pnl|last] [--json]\n"
    "  kase-pilot watch [--follow]\n"
    "  kase-pilot orders [--all]\n"
    "  kase-pilot trades --from YYYY-MM-DD --to YYYY-MM-DD "
    "[--symbol SYMBOL] [--limit NUMBER] [--json]\n"
    "  kase-pilot candles SYMBOL [--from YYYY-MM-DD] [--to YYYY-MM-DD] "
    "[--timeframe SECONDS]"
)

_PORTFOLIO_NAME_WIDTH = 28
_PORTFOLIO_SORT_FIELDS = {"ticker", "value", "pnl", "last"}
WATCH_REFRESH_SECONDS = 5


def _valid_number(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None

    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _format_number(value: object, decimal_places: int | None = None) -> str:
    number = _valid_number(value)
    if number is None:
        return "-"

    if decimal_places is not None:
        return format(number, f".{decimal_places}f")
    if number == 0:
        return "0"
    rendered = format(number, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _format_signed_number(value: object) -> str:
    number = _valid_number(value)
    return format(number, "+.2f") if number is not None else "-"


def _format_text(value: object) -> str:
    return value if isinstance(value, str) else "-"


def _format_portfolio_name(value: object) -> str:
    if not isinstance(value, str) or not value:
        return "-"
    if len(value) <= _PORTFOLIO_NAME_WIDTH:
        return value
    return value[: _PORTFOLIO_NAME_WIDTH - 3] + "..."


def _mapping_rows(value: object) -> list[Mapping[object, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _portfolio_rows(
    summary: object,
) -> tuple[list[Mapping[object, object]], list[Mapping[object, object]]]:
    result = summary.get("result") if isinstance(summary, Mapping) else None
    position_state = result.get("ps") if isinstance(result, Mapping) else None
    positions = (
        _mapping_rows(position_state.get("pos"))
        if isinstance(position_state, Mapping)
        else []
    )
    cash_balances = (
        _mapping_rows(position_state.get("acc"))
        if isinstance(position_state, Mapping)
        else []
    )
    return positions, cash_balances


def _sort_portfolio_positions(
    positions: list[Mapping[object, object]],
    sort_field: str | None,
) -> list[Mapping[object, object]]:
    if sort_field is None:
        return positions
    if sort_field == "ticker":

        def ticker_key(position: Mapping[object, object]) -> tuple[int, str]:
            ticker = position.get("i")
            if isinstance(ticker, str) and ticker:
                return 0, ticker.casefold()
            return 1, ""

        return sorted(positions, key=ticker_key)

    field = {
        "value": "market_value",
        "pnl": "profit_close",
        "last": "mkt_price",
    }[sort_field]
    descending = sort_field in {"value", "last"}

    def numeric_key(position: Mapping[object, object]) -> tuple[int, Decimal]:
        number = _valid_number(position.get(field))
        if number is None:
            return 1, Decimal()
        return 0, -number if descending else number

    return sorted(positions, key=numeric_key)


def _filter_portfolio_positions(
    positions: list[Mapping[object, object]],
    symbol: str | None,
) -> list[Mapping[object, object]]:
    if symbol is None:
        return positions
    normalized_symbol = symbol.casefold()
    return [
        position
        for position in positions
        if isinstance((ticker := position.get("i")), str)
        and bool(ticker)
        and ticker.casefold() == normalized_symbol
    ]


def _prepare_portfolio_positions(
    positions: list[Mapping[object, object]],
    symbol: str | None,
    sort_field: str | None,
) -> tuple[
    list[Mapping[object, object]],
    list[Mapping[object, object]],
]:
    filtered_positions = _filter_portfolio_positions(positions, symbol)
    displayed_positions = _sort_portfolio_positions(filtered_positions, sort_field)
    return filtered_positions, displayed_positions


def _portfolio_totals(
    positions: list[Mapping[object, object]],
) -> dict[str, list[Decimal | None]]:
    totals: dict[str, list[Decimal | None]] = {}
    for position in positions:
        currency = position.get("curr")
        if not isinstance(currency, str) or not currency:
            continue
        aggregate = totals.setdefault(currency, [None, None])
        market_value = _valid_number(position.get("market_value"))
        profit_loss = _valid_number(position.get("profit_close"))
        if market_value is not None:
            aggregate[0] = (aggregate[0] or Decimal()) + market_value
        if profit_loss is not None:
            aggregate[1] = (aggregate[1] or Decimal()) + profit_loss
    return totals


def _format_portfolio(
    summary: object,
    sort_field: str | None = None,
    symbol: str | None = None,
) -> str:
    positions, cash_balances = _portfolio_rows(summary)
    filtered_positions, displayed_positions = _prepare_portfolio_positions(
        positions,
        symbol,
        sort_field,
    )
    totals = _portfolio_totals(filtered_positions)

    lines = ["Portfolio", ""]
    if displayed_positions:
        header = (
            f"{'Ticker':<14} {'Name':<{_PORTFOLIO_NAME_WIDTH}} "
            f"{'Qty':>12} {'Avg':>12} {'Last':>12} {'P/L':>12} "
            f"{'Value':>12} {'Currency':>10}"
        )
        lines.extend((header, "-" * len(header)))
        for position in displayed_positions:
            lines.append(
                f"{_format_text(position.get('i')):<14} "
                f"{_format_portfolio_name(position.get('name')):<{_PORTFOLIO_NAME_WIDTH}} "
                f"{_format_number(position.get('q')):>12} "
                f"{_format_number(position.get('price_a'), 2):>12} "
                f"{_format_number(position.get('mkt_price'), 2):>12} "
                f"{_format_number(position.get('profit_close'), 2):>12} "
                f"{_format_number(position.get('market_value'), 2):>12} "
                f"{_format_text(position.get('curr')):>10}"
            )
    else:
        lines.append("No positions.")

    lines.extend(("", "Totals", ""))
    valid_totals = [
        (currency, aggregate)
        for currency, aggregate in totals.items()
        if aggregate[0] is not None or aggregate[1] is not None
    ]
    if valid_totals:
        header = f"{'Currency':<14} {'Value':>12} {'P/L':>12}"
        lines.extend((header, "-" * len(header)))
        for currency, aggregate in valid_totals:
            market_value = (
                format(aggregate[0], ".2f") if aggregate[0] is not None else "-"
            )
            profit_loss = (
                format(aggregate[1], ".2f") if aggregate[1] is not None else "-"
            )
            lines.append(f"{currency:<14} {market_value:>12} {profit_loss:>12}")
    else:
        lines.append("No totals.")

    lines.extend(("", "Cash", ""))
    if cash_balances:
        header = f"{'Currency':<14} {'Balance':>12}"
        lines.extend((header, "-" * len(header)))
        for balance in cash_balances:
            lines.append(
                f"{_format_text(balance.get('curr')):<14} "
                f"{_format_number(balance.get('s'), 2):>12}"
            )
    else:
        lines.append("No cash balances.")

    return "\n".join(lines)


def _json_decimal(value: object) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return None
    return number if number.is_finite() else None


def _json_number(value: object) -> int | float | None:
    number = _json_decimal(value)
    if number is None:
        return None
    if number == number.to_integral_value():
        return int(number)
    result = float(number)
    return result if math.isfinite(result) else None


def _json_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _portfolio_json_totals(
    positions: list[Mapping[object, object]],
) -> dict[str, list[Decimal | None]]:
    totals: dict[str, list[Decimal | None]] = {}
    for position in positions:
        currency = position.get("curr")
        if not isinstance(currency, str) or not currency:
            continue
        aggregate = totals.setdefault(currency, [None, None])
        market_value = _json_decimal(position.get("market_value"))
        profit_loss = _json_decimal(position.get("profit_close"))
        if market_value is not None:
            aggregate[0] = (aggregate[0] or Decimal()) + market_value
        if profit_loss is not None:
            aggregate[1] = (aggregate[1] or Decimal()) + profit_loss
    return totals


def _portfolio_json(
    summary: object,
    sort_field: str | None = None,
    symbol: str | None = None,
) -> dict[str, object]:
    positions, cash_balances = _portfolio_rows(summary)
    filtered_positions, displayed_positions = _prepare_portfolio_positions(
        positions,
        symbol,
        sort_field,
    )
    totals = _portfolio_json_totals(filtered_positions)

    return {
        "positions": [
            {
                "ticker": _json_string(position.get("i")),
                "name": _json_string(position.get("name")),
                "quantity": _json_number(position.get("q")),
                "average_price": _json_number(position.get("price_a")),
                "last_price": _json_number(position.get("mkt_price")),
                "profit_loss": _json_number(position.get("profit_close")),
                "market_value": _json_number(position.get("market_value")),
                "currency": _json_string(position.get("curr")),
            }
            for position in displayed_positions
        ],
        "totals": [
            {
                "currency": currency,
                "market_value": _json_number(aggregate[0]),
                "profit_loss": _json_number(aggregate[1]),
            }
            for currency, aggregate in totals.items()
            if aggregate[0] is not None or aggregate[1] is not None
        ],
        "cash": [
            {
                "currency": _json_string(balance.get("curr")),
                "balance": _json_number(balance.get("s")),
            }
            for balance in cash_balances
        ],
    }


def _format_watch(summary: object) -> str:
    positions, cash_balances = _portfolio_rows(summary)

    lines = ["Portfolio", ""]
    if positions:
        header = f"{'Ticker':<18} {'Last':>12} {'P/L':>12}"
        lines.extend((header, "-" * len(header)))
        for position in positions:
            lines.append(
                f"{_format_text(position.get('i')):<18} "
                f"{_format_number(position.get('mkt_price'), 2):>12} "
                f"{_format_signed_number(position.get('profit_close')):>12}"
            )
    else:
        lines.append("No positions.")

    lines.extend(("", "Cash", ""))
    non_zero_cash = [
        (balance, number)
        for balance in cash_balances
        if (number := _valid_number(balance.get("s"))) is not None and number != 0
    ]
    if non_zero_cash:
        header = f"{'Currency':<18} {'Balance':>12}"
        lines.extend((header, "-" * len(header)))
        for balance, number in non_zero_cash:
            lines.append(
                f"{_format_text(balance.get('curr')):<18} "
                f"{format(number, '.2f'):>12}"
            )
    else:
        lines.append("No cash balances.")

    return "\n".join(lines)


def _clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def _run_info(
    public_key: str,
    private_key: str,
    ticker: str,
    *,
    sup: bool,
) -> int:
    use_case = create_get_security_info(public_key, private_key)
    result = use_case.execute(ticker, sup=sup)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_quotes(public_key: str, private_key: str, ticker: str) -> int:
    use_case = create_get_current_quotes(public_key, private_key)
    result = use_case.execute([ticker])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_search(public_key: str, private_key: str, query: str) -> int:
    use_case = create_find_instrument(public_key, private_key)
    result = use_case.execute(query)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_symbols(
    public_key: str,
    private_key: str,
    *,
    exchange: str | None,
) -> int:
    use_case = create_get_symbols(public_key, private_key)
    if exchange is None:
        result = use_case.execute()
    else:
        result = use_case.execute(exchange=exchange)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_news(
    public_key: str,
    private_key: str,
    query: str,
    *,
    symbol: str | None,
    story_id: str | None,
    limit: int,
) -> int:
    use_case = create_get_news(public_key, private_key)
    result = use_case.execute(
        query,
        symbol=symbol,
        story_id=story_id,
        limit=limit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_market_status(
    public_key: str,
    private_key: str,
    *,
    market: str,
    mode: str | None,
) -> int:
    use_case = create_get_market_status(public_key, private_key)
    result = use_case.execute(market, mode=mode)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_top(
    public_key: str,
    private_key: str,
    *,
    instrument_type: str,
    exchange: str,
    gainers: bool,
    limit: int,
) -> int:
    use_case = create_get_most_traded(public_key, private_key)
    result = use_case.execute(
        instrument_type,
        exchange=exchange,
        gainers=gainers,
        limit=limit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_orders_history(
    public_key: str,
    private_key: str,
    *,
    start: datetime | None,
    end: datetime | None,
) -> int:
    use_case = create_get_historical(public_key, private_key)
    arguments: dict[str, datetime] = {}
    if start is not None:
        arguments["start"] = start
    if end is not None:
        arguments["end"] = end
    result = use_case.execute(**arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_corporate_actions(
    public_key: str,
    private_key: str,
    *,
    reception: int,
) -> int:
    use_case = create_get_corporate_actions(public_key, private_key)
    result = use_case.execute(reception)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_price_alerts(
    public_key: str,
    private_key: str,
    *,
    symbol: str | None,
) -> int:
    use_case = create_get_price_alerts(public_key, private_key)
    if symbol is None:
        result = use_case.execute()
    else:
        result = use_case.execute(symbol=symbol)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_requests_history(
    public_key: str,
    private_key: str,
    *,
    doc_id: int | None,
    exec_id: int | None,
    start: date | datetime | None,
    end: date | datetime | None,
    limit: int | None,
    offset: int | None,
    status: int | None,
) -> int:
    use_case = create_get_requests_history(public_key, private_key)
    arguments: dict[str, object] = {}
    if doc_id is not None:
        arguments["doc_id"] = doc_id
    if exec_id is not None:
        arguments["exec_id"] = exec_id
    if start is not None:
        arguments["start"] = start
    if end is not None:
        arguments["end"] = end
    if limit is not None:
        arguments["limit"] = limit
    if offset is not None:
        arguments["offset"] = offset
    if status is not None:
        arguments["status"] = status
    result = use_case.execute(**arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_broker_report(
    public_key: str,
    private_key: str,
    *,
    start: date | None,
    end: date | None,
    period: datetime_time | None,
) -> int:
    use_case = create_get_broker_report(public_key, private_key)
    arguments: dict[str, object] = {}
    if start is not None:
        arguments["start"] = start
    if end is not None:
        arguments["end"] = end
    if period is not None:
        arguments["period"] = period
    result = use_case.execute(**arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_user(public_key: str, private_key: str) -> int:
    use_case = create_get_user_info(public_key, private_key)
    result = use_case.execute()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_summary(public_key: str, private_key: str) -> int:
    use_case = create_get_account_summary(public_key, private_key)
    result = use_case.execute()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_portfolio(
    public_key: str,
    private_key: str,
    *,
    json_output: bool,
    sort_field: str | None,
    symbol: str | None,
) -> int:
    use_case = create_get_account_summary(public_key, private_key)
    result = use_case.execute()
    if json_output:
        print(
            json.dumps(
                _portfolio_json(result, sort_field=sort_field, symbol=symbol),
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(_format_portfolio(result, sort_field=sort_field, symbol=symbol))
    return 0


def _run_watch(
    public_key: str,
    private_key: str,
    *,
    follow: bool,
) -> int:
    use_case = create_get_account_summary(public_key, private_key)
    if follow:
        try:
            while True:
                result = use_case.execute()
                _clear_terminal()
                print(_format_watch(result))
                time.sleep(WATCH_REFRESH_SECONDS)
        except KeyboardInterrupt:
            return 0
    result = use_case.execute()
    print(_format_watch(result))
    return 0


def _run_orders(
    public_key: str,
    private_key: str,
    *,
    active: bool,
) -> int:
    use_case = create_get_placed_orders(public_key, private_key)
    result = use_case.execute(active=active)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_trades(
    public_key: str,
    private_key: str,
    *,
    start: date | datetime,
    end: date | datetime,
    symbol: str | None,
    limit: int | None,
) -> int:
    use_case = create_get_trades_history(public_key, private_key)
    result = use_case.execute(start, end, symbol=symbol, limit=limit)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def _run_candles(
    public_key: str,
    private_key: str,
    symbol: str,
    *,
    start: date | datetime | None,
    end: date | datetime | None,
    timeframe: int | None,
) -> int:
    use_case = create_get_historical_candles(public_key, private_key)
    arguments: dict[str, object] = {}
    if start is not None:
        arguments["start"] = start
    if end is not None:
        arguments["end"] = end
    if timeframe is not None:
        arguments["timeframe"] = timeframe
    result = use_case.execute(symbol, **arguments)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def run(
    command: str,
    ticker: str | None = None,
    *,
    sup: bool = True,
    active: bool = True,
    follow: bool = False,
    json_output: bool = False,
    sort_field: str | None = None,
    symbol: str | None = None,
    story_id: str | None = None,
    market: str = "*",
    mode: str | None = None,
    instrument_type: str = "stocks",
    exchange: str | None = None,
    gainers: bool = True,
    reception: int = 35,
    doc_id: int | None = None,
    exec_id: int | None = None,
    offset: int | None = None,
    status: int | None = None,
    period: datetime_time | None = None,
    limit: int | None = None,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
    timeframe: int | None = None,
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Execute a broker query and print its CLI representation."""
    if command not in {
        "info",
        "quotes",
        "search",
        "symbols",
        "news",
        "market-status",
        "top",
        "orders-history",
        "corporate-actions",
        "price-alerts",
        "requests-history",
        "broker-report",
        "user",
        "summary",
        "portfolio",
        "watch",
        "orders",
        "trades",
        "candles",
    }:
        raise ValueError(f"Unknown command: {command}")
    if command == "trades" and (ticker is not None or start is None or end is None):
        raise ValueError("The trades command requires a date range")
    if command == "orders-history" and (
        (start is not None and not isinstance(start, datetime))
        or (end is not None and not isinstance(end, datetime))
    ):
        raise ValueError("The orders-history command requires datetime values")
    if sort_field is not None and (
        command != "portfolio" or sort_field not in _PORTFOLIO_SORT_FIELDS
    ):
        raise ValueError(f"Unsupported portfolio sort field: {sort_field}")
    if json_output and command not in {
        "portfolio",
        "trades",
        "news",
        "market-status",
        "top",
        "orders-history",
        "corporate-actions",
        "price-alerts",
        "requests-history",
        "broker-report",
        "symbols",
    }:
        raise ValueError(
            "JSON output is supported only for portfolio, trades, news, "
            "market-status, top, orders-history, corporate-actions, price-alerts, "
            "requests-history, broker-report, and symbols"
        )
    if command == "portfolio" and symbol is not None:
        symbol = symbol.strip()
        if not symbol:
            raise ValueError("Portfolio symbol must not be empty")
    if (
        command
        in {
            "user",
            "summary",
            "portfolio",
            "watch",
            "orders",
            "market-status",
            "top",
            "orders-history",
            "corporate-actions",
            "price-alerts",
            "requests-history",
            "broker-report",
            "symbols",
        }
        and ticker is not None
    ):
        raise ValueError(f"The {command} command does not accept an argument")
    if (
        command
        not in {
            "user",
            "summary",
            "portfolio",
            "watch",
            "orders",
            "trades",
            "market-status",
            "top",
            "orders-history",
            "corporate-actions",
            "price-alerts",
            "requests-history",
            "broker-report",
            "symbols",
        }
        and ticker is None
    ):
        raise ValueError(f"The {command} command requires an argument")

    settings = load_settings(project_root, environ=environ)
    public_key = settings.tradernet_public_key
    private_key = settings.tradernet_private_key
    if command == "info":
        return _run_info(public_key, private_key, ticker, sup=sup)
    if command == "quotes":
        return _run_quotes(public_key, private_key, ticker)
    if command == "search":
        return _run_search(public_key, private_key, ticker)
    if command == "symbols":
        return _run_symbols(
            public_key,
            private_key,
            exchange=exchange,
        )
    if command == "news":
        return _run_news(
            public_key,
            private_key,
            ticker,
            symbol=symbol,
            story_id=story_id,
            limit=30 if limit is None else limit,
        )
    if command == "market-status":
        return _run_market_status(
            public_key,
            private_key,
            market=market,
            mode=mode,
        )
    if command == "top":
        return _run_top(
            public_key,
            private_key,
            instrument_type=instrument_type,
            exchange="usa" if exchange is None else exchange,
            gainers=gainers,
            limit=10 if limit is None else limit,
        )
    if command == "orders-history":
        return _run_orders_history(
            public_key,
            private_key,
            start=start,
            end=end,
        )
    if command == "corporate-actions":
        return _run_corporate_actions(
            public_key,
            private_key,
            reception=reception,
        )
    if command == "price-alerts":
        return _run_price_alerts(
            public_key,
            private_key,
            symbol=symbol,
        )
    if command == "requests-history":
        return _run_requests_history(
            public_key,
            private_key,
            doc_id=doc_id,
            exec_id=exec_id,
            start=start,
            end=end,
            limit=limit,
            offset=offset,
            status=status,
        )
    if command == "broker-report":
        return _run_broker_report(
            public_key,
            private_key,
            start=start,
            end=end,
            period=period,
        )
    if command == "user":
        return _run_user(public_key, private_key)
    if command == "summary":
        return _run_summary(public_key, private_key)
    if command == "portfolio":
        return _run_portfolio(
            public_key,
            private_key,
            json_output=json_output,
            sort_field=sort_field,
            symbol=symbol,
        )
    if command == "watch":
        return _run_watch(public_key, private_key, follow=follow)
    if command == "orders":
        return _run_orders(public_key, private_key, active=active)
    if command == "trades":
        return _run_trades(
            public_key,
            private_key,
            start=start,
            end=end,
            symbol=symbol,
            limit=limit,
        )
    if command == "candles":
        return _run_candles(
            public_key,
            private_key,
            ticker,
            start=start,
            end=end,
            timeframe=timeframe,
        )
    raise ValueError(f"Unknown command: {command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Provide the application process boundary."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments in (["-h"], ["--help"]):
        print(_USAGE)
        return 0
    if arguments == ["--version"]:
        print(__version__)
        return 0

    start = None
    end = None
    symbol = None
    story_id = None
    market = "*"
    mode = None
    instrument_type = "stocks"
    exchange = "usa"
    symbols_exchange = None
    gainers = True
    reception = 35
    doc_id = None
    exec_id = None
    offset = None
    status = None
    period = None
    limit = None
    timeframe = None
    sort_field = None
    json_output = False
    if arguments in (
        ["user"],
        ["summary"],
        ["portfolio"],
        ["watch"],
        ["watch", "--follow"],
        ["orders"],
        ["orders", "--all"],
        ["market-status"],
        ["top"],
        ["orders-history"],
        ["corporate-actions"],
        ["price-alerts"],
        ["requests-history"],
        ["broker-report"],
        ["symbols"],
    ) or (
        len(arguments) == 2
        and arguments[0]
        in {
            "info",
            "quotes",
            "search",
            "candles",
        }
    ):
        pass
    elif arguments and arguments[0] == "portfolio":
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in {"--symbol", "--sort", "--json"}:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag == "--sort":
                if value not in _PORTFOLIO_SORT_FIELDS:
                    print(_USAGE, file=sys.stderr)
                    return 2
                sort_field = value
            else:
                symbol = value.strip()
                if not symbol:
                    print(_USAGE, file=sys.stderr)
                    return 2
            index += 2
    elif arguments and arguments[0] == "news":
        news_flags = {"--symbol", "--story-id", "--limit", "--json"}
        if len(arguments) < 2 or arguments[1].startswith("--"):
            print(_USAGE, file=sys.stderr)
            return 2

        seen_flags: set[str] = set()
        index = 2
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in news_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag == "--symbol":
                symbol = value
            elif flag == "--story-id":
                story_id = value
            else:
                try:
                    limit = int(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2
                if limit <= 0:
                    print(_USAGE, file=sys.stderr)
                    return 2
            index += 2
    elif arguments and arguments[0] == "market-status":
        market_status_flags = {"--market", "--mode", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in market_status_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag == "--market":
                market = value
            else:
                mode = value
            index += 2
    elif arguments and arguments[0] == "symbols":
        symbols_flags = {"--exchange", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in symbols_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            symbols_exchange = arguments[index + 1]
            index += 2
    elif arguments and arguments[0] == "top":
        top_flags = {"--type", "--exchange", "--limit", "--losers", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in top_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--losers":
                gainers = False
                index += 1
                continue
            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag == "--type":
                instrument_type = value
            elif flag == "--exchange":
                exchange = value
            else:
                try:
                    limit = int(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2
                if limit <= 0:
                    print(_USAGE, file=sys.stderr)
                    return 2
            index += 2
    elif arguments and arguments[0] == "orders-history":
        history_flags = {"--start", "--end", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in history_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            try:
                parsed_datetime = datetime.fromisoformat(arguments[index + 1])
            except ValueError:
                print(_USAGE, file=sys.stderr)
                return 2
            if flag == "--start":
                start = parsed_datetime
            else:
                end = parsed_datetime
            index += 2
    elif arguments and arguments[0] == "corporate-actions":
        corporate_action_flags = {"--reception", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in corporate_action_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            try:
                reception = int(arguments[index + 1])
            except ValueError:
                print(_USAGE, file=sys.stderr)
                return 2
            if reception <= 0:
                print(_USAGE, file=sys.stderr)
                return 2
            index += 2
    elif arguments and arguments[0] == "price-alerts":
        price_alert_flags = {"--symbol", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in price_alert_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            symbol = arguments[index + 1]
            index += 2
    elif arguments and arguments[0] == "requests-history":
        request_history_flags = {
            "--doc-id",
            "--exec-id",
            "--start",
            "--end",
            "--limit",
            "--offset",
            "--status",
            "--json",
        }
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in request_history_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag in {"--start", "--end"}:
                try:
                    parsed_datetime = datetime.fromisoformat(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2
                if flag == "--start":
                    start = parsed_datetime
                else:
                    end = parsed_datetime
            else:
                try:
                    parsed_integer = int(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2
                if flag == "--limit":
                    if parsed_integer <= 0:
                        print(_USAGE, file=sys.stderr)
                        return 2
                    limit = parsed_integer
                elif flag == "--offset":
                    if parsed_integer < 0:
                        print(_USAGE, file=sys.stderr)
                        return 2
                    offset = parsed_integer
                elif flag == "--doc-id":
                    doc_id = parsed_integer
                elif flag == "--exec-id":
                    exec_id = parsed_integer
                else:
                    status = parsed_integer
            index += 2
    elif arguments and arguments[0] == "broker-report":
        broker_report_flags = {"--start", "--end", "--period", "--json"}
        seen_flags: set[str] = set()
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in broker_report_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            try:
                if flag == "--period":
                    period = datetime_time.fromisoformat(value)
                else:
                    parsed_date = date.fromisoformat(value)
                    if flag == "--start":
                        start = parsed_date
                    else:
                        end = parsed_date
            except ValueError:
                print(_USAGE, file=sys.stderr)
                return 2
            index += 2
    elif arguments and arguments[0] == "trades":
        seen_flags: set[str] = set()
        trades_flags = {"--from", "--to", "--symbol", "--limit", "--json"}
        index = 1
        while index < len(arguments):
            flag = arguments[index]
            if flag in seen_flags or flag not in trades_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            if flag == "--json":
                json_output = True
                index += 1
                continue
            if index + 1 >= len(arguments) or arguments[index + 1] in trades_flags:
                print(_USAGE, file=sys.stderr)
                return 2
            value = arguments[index + 1]
            if flag == "--symbol":
                symbol = value
            elif flag == "--limit":
                try:
                    limit = int(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2
            else:
                try:
                    parsed_date = date.fromisoformat(value)
                except ValueError:
                    print(_USAGE, file=sys.stderr)
                    return 2

                if flag == "--from":
                    start = parsed_date
                else:
                    end = parsed_date
            index += 2

        if not {"--from", "--to"}.issubset(seen_flags):
            print(_USAGE, file=sys.stderr)
            return 2
    elif len(arguments) >= 4 and len(arguments) % 2 == 0 and arguments[0] == "candles":
        seen_flags: set[str] = set()
        for index in range(2, len(arguments), 2):
            flag = arguments[index]
            value = arguments[index + 1]
            if flag in seen_flags or flag not in {"--from", "--to", "--timeframe"}:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

            try:
                if flag == "--timeframe":
                    timeframe = int(value)
                else:
                    parsed_date = datetime.fromisoformat(value)
                    if parsed_date.date().isoformat() != value:
                        raise ValueError
                    if flag == "--from":
                        start = parsed_date
                    else:
                        end = parsed_date
            except ValueError:
                print(_USAGE, file=sys.stderr)
                return 2
    else:
        print(_USAGE, file=sys.stderr)
        return 2

    run_arguments: dict[str, object] = {}
    if start is not None:
        run_arguments["start"] = start
    if end is not None:
        run_arguments["end"] = end
    if timeframe is not None:
        run_arguments["timeframe"] = timeframe

    try:
        if arguments == ["orders", "--all"]:
            return run("orders", active=False)
        if arguments == ["watch", "--follow"]:
            return run("watch", follow=True)
        if arguments[0] == "portfolio" and (
            symbol is not None or sort_field is not None or json_output
        ):
            portfolio_arguments: dict[str, object] = {}
            if symbol is not None:
                portfolio_arguments["symbol"] = symbol
            if sort_field is not None:
                portfolio_arguments["sort_field"] = sort_field
            if json_output:
                portfolio_arguments["json_output"] = True
            return run("portfolio", **portfolio_arguments)
        if arguments[0] in {
            "user",
            "summary",
            "portfolio",
            "watch",
            "orders",
            "market-status",
            "top",
            "orders-history",
            "corporate-actions",
            "price-alerts",
            "requests-history",
            "broker-report",
            "symbols",
        } and arguments == [arguments[0]]:
            return run(arguments[0])
        if arguments[0] == "trades":
            trades_arguments: dict[str, object] = {
                "start": start,
                "end": end,
                "symbol": symbol,
                "limit": limit,
            }
            if json_output:
                trades_arguments["json_output"] = True
            return run("trades", **trades_arguments)
        if arguments[0] == "news":
            news_arguments: dict[str, object] = {
                "symbol": symbol,
                "story_id": story_id,
                "limit": 30 if limit is None else limit,
            }
            if json_output:
                news_arguments["json_output"] = True
            return run("news", arguments[1], **news_arguments)
        if arguments[0] == "market-status":
            market_status_arguments: dict[str, object] = {
                "market": market,
                "mode": mode,
            }
            if json_output:
                market_status_arguments["json_output"] = True
            return run("market-status", **market_status_arguments)
        if arguments[0] == "symbols":
            symbols_arguments: dict[str, object] = {}
            if symbols_exchange is not None:
                symbols_arguments["exchange"] = symbols_exchange
            if json_output:
                symbols_arguments["json_output"] = True
            return run("symbols", **symbols_arguments)
        if arguments[0] == "top":
            top_arguments: dict[str, object] = {
                "instrument_type": instrument_type,
                "exchange": exchange,
                "gainers": gainers,
                "limit": 10 if limit is None else limit,
            }
            if json_output:
                top_arguments["json_output"] = True
            return run("top", **top_arguments)
        if arguments[0] == "orders-history":
            history_arguments: dict[str, object] = {}
            if start is not None:
                history_arguments["start"] = start
            if end is not None:
                history_arguments["end"] = end
            if json_output:
                history_arguments["json_output"] = True
            return run("orders-history", **history_arguments)
        if arguments[0] == "corporate-actions":
            corporate_actions_arguments: dict[str, object] = {
                "reception": reception,
            }
            if json_output:
                corporate_actions_arguments["json_output"] = True
            return run("corporate-actions", **corporate_actions_arguments)
        if arguments[0] == "price-alerts":
            price_alert_arguments: dict[str, object] = {}
            if symbol is not None:
                price_alert_arguments["symbol"] = symbol
            if json_output:
                price_alert_arguments["json_output"] = True
            return run("price-alerts", **price_alert_arguments)
        if arguments[0] == "requests-history":
            request_history_arguments: dict[str, object] = {}
            if doc_id is not None:
                request_history_arguments["doc_id"] = doc_id
            if exec_id is not None:
                request_history_arguments["exec_id"] = exec_id
            if start is not None:
                request_history_arguments["start"] = start
            if end is not None:
                request_history_arguments["end"] = end
            if limit is not None:
                request_history_arguments["limit"] = limit
            if offset is not None:
                request_history_arguments["offset"] = offset
            if status is not None:
                request_history_arguments["status"] = status
            if json_output:
                request_history_arguments["json_output"] = True
            return run("requests-history", **request_history_arguments)
        if arguments[0] == "broker-report":
            broker_report_arguments: dict[str, object] = {}
            if start is not None:
                broker_report_arguments["start"] = start
            if end is not None:
                broker_report_arguments["end"] = end
            if period is not None:
                broker_report_arguments["period"] = period
            if json_output:
                broker_report_arguments["json_output"] = True
            return run("broker-report", **broker_report_arguments)
        return run(arguments[0], arguments[1], **run_arguments)
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
