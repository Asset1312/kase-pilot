"""Application entry point."""

import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

from kase_pilot.app import create_get_security_info
from kase_pilot.core.config import load_settings


def run(
    ticker: str,
    *,
    sup: bool = True,
    project_root: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """Retrieve and print information about one broker instrument."""
    settings = load_settings(project_root, environ=environ)
    get_security_info = create_get_security_info(
        settings.tradernet_public_key,
        settings.tradernet_private_key,
    )
    result = get_security_info.execute(ticker, sup=sup)
    print(json.dumps(result))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Provide the application process boundary."""
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 1:
        print("Usage: kase-pilot TICKER", file=sys.stderr)
        return 2

    return run(arguments[0])


if __name__ == "__main__":
    main()
