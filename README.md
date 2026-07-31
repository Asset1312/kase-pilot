# KASE Pilot

KASE Pilot is a command-line client for read-only Tradernet account and
KASE-related market data. It is an independent project and is not affiliated
with Tradernet. Version 1.0.0rc1 does not place or cancel orders.

## Compatibility contract

KASE Pilot 1.0 provides a stable CLI compatibility contract. The contract
covers documented command names and options, output modes and JSON formatting,
exit codes, and documented CLI behavior.

Python subpackages, classes, services, adapters, use cases, constructors, and
raw Tradernet SDK response schemas are internal or provisional. They may change
without the compatibility guarantees applied to the CLI.

## Requirements

- Python 3.14 or newer
- Tradernet account and API credentials

Operating-system support is not formally guaranteed.

## Installation

Install the project from a local source checkout. Replace `<repository-url>`
with the actual repository URL:

```console
git clone <repository-url>
cd KASE-Pilot
python -m venv .venv
```

Activate the environment in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or activate it on Linux or macOS:

```sh
source .venv/bin/activate
```

Install KASE Pilot in editable mode:

```console
python -m pip install --upgrade pip
python -m pip install -e .
```

For local development and release validation, install the project tools into
the activated `.venv`:

```console
python -m pip install black ruff pytest build twine
```

## Credentials

Every data command requires these environment variables:

- `TRADERNET_PUBLIC_KEY`
- `TRADERNET_PRIVATE_KEY`

Set them for the current Windows PowerShell session:

```powershell
$env:TRADERNET_PUBLIC_KEY = "..."
$env:TRADERNET_PRIVATE_KEY = "..."
```

Or for the current Linux or macOS shell session:

```sh
export TRADERNET_PUBLIC_KEY="..."
export TRADERNET_PRIVATE_KEY="..."
```

Never commit credentials or place real credentials in examples or tracked
files. Prefer session environment variables or a secure secrets mechanism.
KASE Pilot does not currently load credentials from a `.env` file.

## CLI invocation

After installation, invoke the console script as:

```console
kase-pilot COMMAND [OPTIONS]
```

If the editable console script is unavailable, the package also supports:

```console
python -m kase_pilot.main COMMAND [OPTIONS]
```

Display Usage or the installed version without credentials:

```console
kase-pilot --help
kase-pilot --version
```

## CLI validation

Invalid syntax prints Usage and exits with status `2`. Parsing failures are
handled before credentials are loaded or application objects are composed.
Required arguments and options must be present; duplicate options, unknown
flags, and unexpected positional arguments are rejected. Boolean flags take no
value.

Numeric validation is command-specific and follows the verified Tradernet SDK
contract for each operation. Empty or whitespace-only values are rejected only
where the command explicitly implements that rule, currently for the
`portfolio` symbol filter and the required `instruments` market. Other string
values are not uniformly normalized or rejected.

Help is global: use `kase-pilot --help`. Command-specific forms such as
`kase-pilot symbols --help` are unsupported and are treated as invalid usage.

Raw JSON commands preserve the Tradernet response shape and use the output
format described below. Explicitly documented exceptions may transform the
response; notably, `portfolio --json` emits normalized portfolio JSON.

## Commands

Values explicitly shown as `YYYY-MM-DD` are parsed as ISO dates. Options
accepting `DATETIME` use `datetime.fromisoformat()` and accept a date-only
value or an ISO date and time. The `requests-history --start` and `--end`
options use the same datetime parser despite their `DATE` label.
`broker-report --period` accepts an ISO time supported by
`time.fromisoformat()`.

Duplicate options, missing option values, and unsupported arguments are
invalid CLI usage.

### Account and portfolio

`portfolio` prints a readable portfolio, totals, and cash report. It can
filter a complete ticker case-insensitively, sort position rows, or emit
normalized JSON.

```console
kase-pilot portfolio --symbol HSBK.KZ --sort pnl
```

Options: `--symbol SYMBOL`, `--sort ticker|value|pnl|last`, `--json`.

`watch` prints a compact portfolio snapshot; follow mode refreshes it every
five seconds until interrupted.

```console
kase-pilot watch --follow
```

Option: `--follow`.

`user` prints raw user information.

```console
kase-pilot user
```

No command-specific options.

`summary` prints the raw account-summary response.

```console
kase-pilot summary
```

No command-specific options.

`user-data` prints the raw initial user-data response, including the sections
provided by Tradernet for the current account.

```console
kase-pilot user-data
```

Option: `--json`.

`check-missing-fields` checks for missing profile fields for a required step
and office.

```console
kase-pilot check-missing-fields --step 3 --office Almaty
```

Options: required `--step STEP` and `--office OFFICE`; optional `--json`.

`profile-fields` prints profile fields for a required reception number.

```console
kase-pilot profile-fields --reception 35
```

Options: required `--reception RECEPTION`; optional `--json`.

`price-alerts` prints configured read-only price alerts, optionally filtered
by symbol.

```console
kase-pilot price-alerts --symbol HSBK.KZ
```

Options: `--symbol SYMBOL`, `--json`.

`broker-report` prints a broker report for an optional date range and
end-of-day period.

```console
kase-pilot broker-report --start 2026-01-01 --end 2026-01-31 --period 18:30:15
```

Options: `--start DATE`, `--end DATE`, `--period TIME`, `--json`.

### Orders and trades

`orders` prints active placed orders, or all placed orders with `--all`.

```console
kase-pilot orders --all
```

Option: `--all`.

`orders-history` prints historical orders for an optional ISO datetime range.

```console
kase-pilot orders-history --start 2026-01-01 --end 2026-01-31T18:30:00
```

Options: `--start DATETIME`, `--end DATETIME`, `--json`.

`order-files` prints raw file information for an order or draft order.

```console
kase-pilot order-files --order-id 12345
```

Options: at least one of `--order-id ID` or `--internal-id ID`; optional
`--json`.

`trades` prints trade history for a required ISO date range, with optional
symbol and limit filters.

```console
kase-pilot trades --from 2026-01-01 --to 2026-01-31 --symbol HSBK.KZ --limit 100
```

Options: required `--from YYYY-MM-DD` and `--to YYYY-MM-DD`; optional
`--symbol SYMBOL`, `--limit NUMBER`, `--json`.

`requests-history` prints request history with optional identifiers, range,
pagination, and status filters.

```console
kase-pilot requests-history --start 2026-01-01 --status 3 --limit 100
```

Options: `--doc-id ID`, `--exec-id ID`, `--start DATE`, `--end DATE`,
`--limit LIMIT`, `--offset OFFSET`, `--status STATUS`, `--json`.

### Market data and instruments

`info` prints security information for one ticker.

```console
kase-pilot info HSBK.KZ
```

No command-specific options.

`quotes` prints current quotes for one ticker.

```console
kase-pilot quotes HSBK.KZ
```

No command-specific options.

`search` searches for an instrument using one query argument.

```console
kase-pilot search Halyk
```

No command-specific options.

`symbols` prints instruments from KASE Pilot's local instrument catalog,
optionally limited by exchange. No broker credentials or network access are
required; see `src/kase_pilot/catalog/data/README.md`.

```console
kase-pilot symbols --exchange KASE
```

Options: `--exchange EXCHANGE`, `--json`.

`instruments` prints instruments from KASE Pilot's local instrument catalog
for one required market (a refbook-style code, e.g. `KASE_STOCK` — distinct
from the broader `symbols --exchange` code). No broker credentials or
network access are required; see `src/kase_pilot/catalog/data/README.md`.

```console
kase-pilot instruments --market KASE_STOCK
kase-pilot instruments --market KASE_STOCK --show-expired --json
```

Options: required `--market MARKET`; optional `--show-expired`, `--json`.

`symbol` prints raw information for one security, optionally in a selected
language.

```console
kase-pilot symbol HSBK.KZ --lang en
```

Options: `--lang LANG`, `--json`.

`export-securities` prints a raw export for one or more symbols and can limit
the returned fields.

```console
kase-pilot export-securities HSBK.KZ KZAP.KZ --fields ticker ltp currency
```

Options: `--fields FIELD [FIELD ...]`, `--json`.

`options` prints raw active-options data for an underlying instrument and
exchange.

```console
kase-pilot options AAPL --exchange usa
```

Options: required `--exchange EXCHANGE`; optional `--json`.

`tariffs` prints the raw list of available tariffs.

```console
kase-pilot tariffs
```

Option: `--json`.

`security-sessions` prints raw open security-session data.

```console
kase-pilot security-sessions
```

Option: `--json`.

`candles` prints historical candles for a symbol with optional ISO dates and
timeframe in seconds.

```console
kase-pilot candles HSBK.KZ --from 2026-01-01 --to 2026-01-31 --timeframe 3600
```

Options: `--from YYYY-MM-DD`, `--to YYYY-MM-DD`, `--timeframe SECONDS`.

`market-status` prints raw market-status data.

```console
kase-pilot market-status --market KASE
```

Options: `--market MARKET`, `--mode MODE`, `--json`.

`top` prints raw most-traded market data; `--losers` requests the losers view.

```console
kase-pilot top --type stocks --exchange usa --limit 10 --losers
```

Options: `--type TYPE`, `--exchange EXCHANGE`, `--limit LIMIT`, `--losers`,
`--json`.

`corporate-actions` prints corporate actions for a positive reception period
in days.

```console
kase-pilot corporate-actions --reception 35
```

Options: `--reception DAYS`, `--json`.

## Unsupported command

`news` is retained for future compatibility work but is outside the stable 1.0
CLI contract. Tradernet SDK 2.2.0 cannot currently execute the operation.

```console
kase-pilot news markets --symbol HSBK.KZ --limit 10
```

After validating the command syntax, KASE Pilot prints a concise explanation to
stderr and exits with status `3`. It does not load credentials, compose the use
case, contact Tradernet, or print a traceback.

## Output

Most commands print the Tradernet response as indented UTF-8 JSON:

```python
json.dumps(result, indent=2, ensure_ascii=False)
```

Non-ASCII characters are preserved. For raw-response commands, `--json` is
currently a compatibility flag: plain output and explicit JSON output are
identical. Tradernet response structures may vary and are not a stable schema.

`portfolio` prints a human-readable table by default and normalized JSON with
`--json`. `watch` prints a compact text snapshot. These two commands are the
exceptions to the raw JSON output described above.

## Exit codes

- `0`: success
- `1`: configuration error, including missing credentials
- `2`: invalid CLI usage
- `3`: expected broker or API operation failure

Expected broker and API failures print a concise message to stderr without a
traceback. Unexpected programming errors continue to propagate normally.

## Known limitations

- `news` is explicitly unsupported by the stable 1.0 CLI contract because the
  operation fails inside the external Tradernet SDK. Invocation is rejected
  deterministically before credentials or SDK access.
- `symbols` and `instruments` are served entirely from KASE Pilot's local,
  bundled instrument catalog (see `src/kase_pilot/catalog/data/README.md`)
  and do not depend on the Tradernet API or credentials. The catalog is
  currently a small, manually curated seed, not a complete instrument list.
- KASE Pilot does not place or cancel orders.
- Read-only behavior depends on Tradernet API availability and account
  permissions.
- Python 3.14 is the supported target for this release.

## Development checks

Run the project checks with:

```console
python -m black --check .
python -m ruff check .
python -m pytest
```

Run these commands from the activated `.venv`. For documentation-only changes,
run `git diff --check`. Use targeted tests for localized code changes, and run
the full suite before creating a release tag.

## License

KASE Pilot is licensed under the [MIT License](LICENSE).
