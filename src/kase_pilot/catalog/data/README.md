# Local instrument catalog

## Purpose

`instruments.json` is KASE Pilot's own, project-bundled reference data for
the `symbols` and `instruments` CLI commands. It replaces the previous
dependency on `Tradernet.symbols()` and `Tradernet.get_all()`, both of which
are confirmed to call broker endpoints that return HTTP 404 with no known
replacement (see `docs/API_NOTES.md`). This file is read from disk as a
packaged resource; no network request is ever made to populate it.

The schema below is defined by KASE Pilot itself. It does not mirror any
Tradernet/Freedom response shape, confirmed or otherwise.

## File format

```json
{
  "version": 2,
  "generated": "2026-07-30",
  "source": "free-text description of how this file's contents were produced",
  "instruments": [
    {
      "ticker": "HSBK.KZ",
      "exchange": "KASE",
      "market": "KASE_STOCK",
      "name": "Halyk Bank",
      "currency": "KZT",
      "expired": false
    }
  ]
}
```

### Top-level fields

| Field | Required | Meaning |
|---|---|---|
| `version` | Yes | Integer schema version. Bump it if the shape of an `instruments` entry changes incompatibly, so future code can branch on it if needed. |
| `generated` | Yes | ISO 8601 date the file was last curated/edited. |
| `source` | Yes | Free-text note on where the data came from (e.g. "manually curated from public reference information"). Never write "Tradernet API" here unless a live, working endpoint was actually the source. |
| `instruments` | Yes | The list of instrument entries described below. |

### Instrument entry fields

`exchange` and `market` are deliberately separate fields — they are not
interchangeable, and conflating them was an earlier mistake in this file.
`exchange` is the broad exchange code matched by `symbols --exchange`.
`market` is the finer-grained reference-book code matched by
`instruments --market` (e.g. the `KASE_STOCK`-style refbook filename
observed in the dead Tradernet endpoint's URL pattern, see
`docs/API_NOTES.md`). Both filters match case-insensitively.

| Field | Required | Meaning |
|---|---|---|
| `ticker` | Yes | The instrument's ticker, in the same `SYMBOL.MARKET`-style form already used elsewhere in KASE Pilot (e.g. `AAPL.US`, `HSBK.KZ`). |
| `exchange` | Yes | Broad exchange code. Matched (case-insensitively) against `symbols --exchange`. |
| `market` | No | Finer-grained refbook-style market code. Matched (case-insensitively) against `instruments --market`. Use `null` if no confirmed code exists yet — an entry with `market: null` simply never matches any `instruments --market` query, it still appears under `symbols`. |
| `name` | No | Human-readable instrument name. Use `null` if not confirmed — never guess. |
| `currency` | No | Settlement currency code. Use `null` if not confirmed. |
| `expired` | No | Boolean. Defaults to "not expired" when absent. Only set `true` for instruments confirmed to no longer be tradable. |

Unknown optional fields must be `null`, not omitted with a guessed value and
not invented. Only include an instrument at all if its `ticker` and
`exchange` are independently confirmed public facts.

## Updating the catalog

This file is maintained by hand, in small, atomic commits — the same way
the rest of the project evolves. There is no automated import today because
no confirmed, working broker endpoint exists to source this data from (see
`docs/API_NOTES.md`). To add or correct an entry:

1. Confirm the `ticker` and `exchange` from a public, verifiable source
   (exchange listing, company filing, well-established public knowledge).
   Only set `market` if a refbook-style code for it is independently
   confirmed; otherwise leave it `null`.
2. Add or edit the entry, leaving any unconfirmed field as `null`.
3. Update `generated` to the date of the edit and, if useful, extend
   `source` with where the new entries came from.
4. Bump `version` only if the *shape* of an entry changes (e.g. a new
   required field is introduced) — not for ordinary data additions.

If a confirmed, working broker/reference-data endpoint is ever found, an
automated importer can be introduced then; it is out of scope until that
endpoint exists.
