"""Application entry point."""

import json
import sys
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

from kase_pilot.app import (
    create_find_instrument,
    create_get_account_summary,
    create_get_current_quotes,
    create_get_historical_candles,
    create_get_placed_orders,
    create_get_security_info,
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
    "  kase-pilot orders\n"
    "  kase-pilot candles SYMBOL [--from YYYY-MM-DD] [--to YYYY-MM-DD] "
    "[--timeframe SECONDS]"
)


def run(
    command: str,
    ticker: str | None = None,
    *,
    sup: bool = True,
    start: datetime | None = None,
    end: datetime | None = None,
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
        "orders",
        "candles",
    }:
        raise ValueError(f"Unknown command: {command}")
    if command in {"user", "summary", "orders"} and ticker is not None:
        raise ValueError(f"The {command} command does not accept an argument")
    if command not in {"user", "summary", "orders"} and ticker is None:
        raise ValueError(f"The {command} command requires an argument")

    settings = load_settings(project_root, environ=environ)
    if command == "orders":
        use_case = create_get_placed_orders(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute()
    elif command == "summary":
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
    timeframe = None
    if arguments in (["user"], ["summary"], ["orders"]) or (
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
        if arguments[0] in {"user", "summary", "orders"}:
            return run(arguments[0])
        return run(arguments[0], arguments[1], **run_arguments)
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
