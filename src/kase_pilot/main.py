"""Application entry point."""

import json
import os
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from kase_pilot.app import (
    create_find_instrument,
    create_get_account_summary,
    create_get_current_quotes,
    create_get_historical_candles,
    create_get_placed_orders,
    create_get_security_info,
    create_get_trades_history,
    create_get_user_info,
)
from kase_pilot.core.config import load_settings
from kase_pilot.core.exceptions import ConfigurationError

_USAGE = (
    "Usage:\n"
    "  kase-pilot info TICKER\n"
    "  kase-pilot quotes TICKER\n"
    "  kase-pilot search QUERY\n"
    "  kase-pilot user\n"
    "  kase-pilot summary\n"
    "  kase-pilot portfolio [--symbol SYMBOL] "
    "[--sort ticker|value|pnl|last]\n"
    "  kase-pilot watch [--follow]\n"
    "  kase-pilot orders [--all]\n"
    "  kase-pilot trades --from YYYY-MM-DD --to YYYY-MM-DD "
    "[--symbol SYMBOL] [--limit NUMBER]\n"
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


def _format_portfolio(
    summary: object,
    sort_field: str | None = None,
    symbol: str | None = None,
) -> str:
    positions, cash_balances = _portfolio_rows(summary)
    filtered_positions = _filter_portfolio_positions(positions, symbol)
    displayed_positions = _sort_portfolio_positions(filtered_positions, sort_field)
    totals: dict[str, list[Decimal | None]] = {}
    for position in filtered_positions:
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


def run(
    command: str,
    ticker: str | None = None,
    *,
    sup: bool = True,
    active: bool = True,
    follow: bool = False,
    sort_field: str | None = None,
    symbol: str | None = None,
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
    if sort_field is not None and (
        command != "portfolio" or sort_field not in _PORTFOLIO_SORT_FIELDS
    ):
        raise ValueError(f"Unsupported portfolio sort field: {sort_field}")
    if command == "portfolio" and symbol is not None:
        symbol = symbol.strip()
        if not symbol:
            raise ValueError("Portfolio symbol must not be empty")
    if (
        command in {"user", "summary", "portfolio", "watch", "orders"}
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
        }
        and ticker is None
    ):
        raise ValueError(f"The {command} command requires an argument")

    settings = load_settings(project_root, environ=environ)
    if command == "orders":
        use_case = create_get_placed_orders(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute(active=active)
    elif command in {"summary", "portfolio", "watch"}:
        use_case = create_get_account_summary(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        if command == "watch" and follow:
            try:
                while True:
                    result = use_case.execute()
                    _clear_terminal()
                    print(_format_watch(result))
                    time.sleep(WATCH_REFRESH_SECONDS)
            except KeyboardInterrupt:
                return 0
        result = use_case.execute()
    elif command == "user":
        use_case = create_get_user_info(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute()
    elif command == "trades":
        use_case = create_get_trades_history(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute(
            start,
            end,
            symbol=symbol,
            limit=limit,
        )
    elif command == "info":
        use_case = create_get_security_info(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute(ticker, sup=sup)
    elif command == "quotes":
        use_case = create_get_current_quotes(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute([ticker])
    elif command == "search":
        use_case = create_find_instrument(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute(ticker)
    elif command == "candles":
        use_case = create_get_historical_candles(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        arguments: dict[str, object] = {}
        if start is not None:
            arguments["start"] = start
        if end is not None:
            arguments["end"] = end
        if timeframe is not None:
            arguments["timeframe"] = timeframe
        result = use_case.execute(ticker, **arguments)
    else:
        raise ValueError(f"Unknown command: {command}")

    if command == "portfolio":
        print(_format_portfolio(result, sort_field=sort_field, symbol=symbol))
    elif command == "watch":
        print(_format_watch(result))
    else:
        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Provide the application process boundary."""
    arguments = sys.argv[1:] if argv is None else argv
    start = None
    end = None
    symbol = None
    limit = None
    timeframe = None
    sort_field = None
    if arguments in (
        ["user"],
        ["summary"],
        ["portfolio"],
        ["watch"],
        ["watch", "--follow"],
        ["orders"],
        ["orders", "--all"],
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
    elif len(arguments) in {3, 5} and arguments[0] == "portfolio":
        seen_flags: set[str] = set()
        for index in range(1, len(arguments), 2):
            flag = arguments[index]
            value = arguments[index + 1]
            if flag in seen_flags or flag not in {"--symbol", "--sort"}:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

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
    elif len(arguments) in {5, 7, 9} and arguments[0] == "trades":
        seen_flags: set[str] = set()
        for index in range(1, len(arguments), 2):
            flag = arguments[index]
            value = arguments[index + 1]
            if flag in seen_flags or flag not in {
                "--from",
                "--to",
                "--symbol",
                "--limit",
            }:
                print(_USAGE, file=sys.stderr)
                return 2
            seen_flags.add(flag)

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
            symbol is not None or sort_field is not None
        ):
            portfolio_arguments: dict[str, object] = {}
            if symbol is not None:
                portfolio_arguments["symbol"] = symbol
            if sort_field is not None:
                portfolio_arguments["sort_field"] = sort_field
            return run("portfolio", **portfolio_arguments)
        if arguments[0] in {"user", "summary", "portfolio", "watch", "orders"}:
            return run(arguments[0])
        if arguments[0] == "trades":
            return run(
                "trades",
                start=start,
                end=end,
                symbol=symbol,
                limit=limit,
            )
        return run(arguments[0], arguments[1], **run_arguments)
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
