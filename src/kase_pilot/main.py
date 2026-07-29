"""Application entry point."""

import json
import sys
from collections.abc import Mapping, Sequence
from datetime import date, datetime
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
    "  kase-pilot portfolio\n"
    "  kase-pilot orders [--all]\n"
    "  kase-pilot trades --from YYYY-MM-DD --to YYYY-MM-DD "
    "[--symbol SYMBOL] [--limit NUMBER]\n"
    "  kase-pilot candles SYMBOL [--from YYYY-MM-DD] [--to YYYY-MM-DD] "
    "[--timeframe SECONDS]"
)


def run(
    command: str,
    ticker: str | None = None,
    *,
    sup: bool = True,
    active: bool = True,
    symbol: str | None = None,
    limit: int | None = None,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
    timeframe: int | None = None,
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Execute a broker query and print its JSON result."""
    if command not in {
        "info",
        "quotes",
        "search",
        "user",
        "summary",
        "portfolio",
        "orders",
        "trades",
        "candles",
    }:
        raise ValueError(f"Unknown command: {command}")
    if command == "trades" and (ticker is not None or start is None or end is None):
        raise ValueError("The trades command requires a date range")
    if command in {"user", "summary", "portfolio", "orders"} and ticker is not None:
        raise ValueError(f"The {command} command does not accept an argument")
    if (
        command
        not in {
            "user",
            "summary",
            "portfolio",
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
    elif command in {"summary", "portfolio"}:
        use_case = create_get_account_summary(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
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
    if arguments in (
        ["user"],
        ["summary"],
        ["portfolio"],
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
        if arguments[0] in {"user", "summary", "portfolio", "orders"}:
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
