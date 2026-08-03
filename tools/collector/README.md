# Running the collector unattended

These wrappers run the streaming commands with `--save --reconnect`, which is
what continuous collection needs: data goes to the local database, and a
dropped connection retries with backoff instead of ending the run.

**Nothing here registers itself.** Setting up a scheduled task changes your
machine's configuration, so the registration commands below are yours to run
and yours to review first.

## Prerequisites

`kase-pilot` must be on `PATH` (install the project, or activate its
virtualenv), and both credentials must be visible to the process:

```cmd
setx TRADERNET_PUBLIC_KEY "your_public_key"
setx TRADERNET_PRIVATE_KEY "your_private_key"
```

`setx` writes to the user environment permanently — the values are stored in
the registry in plain text. If that is not acceptable, set the variables on
the scheduled task itself instead, or keep using `set` in an interactive
session and skip unattended collection.

Open a **new** terminal afterwards; `setx` does not affect the current one.

## Manual run

```cmd
tools\collector\collect-quotes.cmd HSBK.KZ KSPI.KZ
tools\collector\collect-orderbook.cmd HSBK.KZ
```

Both run until interrupted. Quote collection takes several symbols in one
process; order-book collection takes exactly one, because the broker's
market-depth subscription is per-instrument.

## Scheduled task (Windows)

Register a task that starts at logon and keeps running. Review the command
before running it — it creates a persistent scheduled task:

```cmd
schtasks /Create /TN "KASE Pilot quotes" /SC ONLOGON /RL LIMITED ^
  /TR "cmd /c \"D:\KASE-Pilot\tools\collector\collect-quotes.cmd HSBK.KZ >> D:\KASE-Pilot\data\logs\quotes.log 2>&1\""
```

Adjust the path if the project lives elsewhere. Redirecting both streams to a
log file matters: without it, reconnection notices and errors go nowhere and a
silently failing collector looks identical to a quiet market.

Useful follow-ups:

```cmd
schtasks /Query  /TN "KASE Pilot quotes"
schtasks /Run    /TN "KASE Pilot quotes"
schtasks /End    /TN "KASE Pilot quotes"
schtasks /Delete /TN "KASE Pilot quotes" /F
```

## Checking that collection is actually happening

A collector that died looks exactly like a market with no activity, so check
the session and interruption tables rather than assuming:

```cmd
python -c "import sqlite3; c=sqlite3.connect('data/database/market.sqlite3'); print(list(c.execute('SELECT id, stream, started_at, finished_at FROM collector_sessions ORDER BY id DESC LIMIT 5')))"
```

A session with `finished_at` set is over. A session with `finished_at` still
`NULL` is either running or was killed without a clean shutdown — the two are
indistinguishable from the database alone, so cross-check that the process is
alive.

Reconnection events are recorded separately:

```cmd
python -c "import sqlite3; c=sqlite3.connect('data/database/market.sqlite3'); print(list(c.execute('SELECT session_id, attempt, failed_at, resumed_at FROM collector_interruptions ORDER BY id DESC LIMIT 10')))"
```

Rows with `resumed_at` set are gaps that closed on their own. A row where it
stays `NULL` means the connection never came back during that session.

## Known limitations

- Log files are not rotated. A long-running collector writing every message to
  a log will grow without bound; rotate or truncate them yourself.
- The database is written with one commit per message, which is fine for the
  message rates observed so far but has not been tested under heavy load.
- Nothing supervises the process itself. If it exits (an unhandled error, a
  reboot, a killed task), collection stops until the task starts it again.
