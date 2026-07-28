"""Application entry point."""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from kase_pilot.app import create_get_current_quotes, create_get_security_info
from kase_pilot.core.config import load_settings
from kase_pilot.core.exceptions import ConfigurationError

_USAGE = "Usage:\n  kase-pilot info TICKER\n  kase-pilot quotes TICKER"


def run(
    command: str,
    ticker: str,
    *,
    sup: bool = True,
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Execute a broker query and print its JSON result."""
    settings = load_settings(project_root, environ=environ)
    if command == "info":
        use_case = create_get_security_info(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute(ticker, sup=sup)
    else:
        use_case = create_get_current_quotes(
            settings.tradernet_public_key,
            settings.tradernet_private_key,
        )
        result = use_case.execute([ticker])

    print(json.dumps(result))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Provide the application process boundary."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 2 or arguments[0] not in {"info", "quotes"}:
        print(_USAGE, file=sys.stderr)
        return 2

    try:
        return run(arguments[0], arguments[1])
    except ConfigurationError as error:
        print(error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
