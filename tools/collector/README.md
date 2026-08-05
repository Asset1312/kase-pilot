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

To start everything at once:

```cmd
tools\collector\collect-all.cmd HSBK.KZ KSPI.KZ
```

Each collector opens in its own console window: one window for quotes (a
single subscription covers all the symbols) and one window per symbol for the
order book, because the broker's market-depth subscription is per-instrument.
Close a window or press Ctrl+C in it to stop that collector; the others keep
running.

Credentials are checked before any window opens, so a missing key fails where
you can see it rather than flashing past in a child window.

To run a single collector in the current window:

```cmd
tools\collector\collect-quotes.cmd HSBK.KZ KSPI.KZ
tools\collector\collect-orderbook.cmd HSBK.KZ
```

Both run until interrupted.

## Collecting continuously, hands-off

`collect-session.cmd` collects both streams without opening console windows,
and keeps running until stopped:

```cmd
tools\collector\collect-session.cmd HSBK.KZ KSPI.KZ
```

Output goes to `data/logs/`, one file per collector, since nothing is watching
a console. The single-collector scripts write to a log too when
`KASE_COLLECT_LOG` names one; otherwise they print to the console as before.

Collecting around the clock is harmless: outside trading hours the broker
simply sends nothing, so the collector idles rather than recording noise. It
also means nothing has to be scheduled to match the exchange calendar, and a
session that runs long or opens early is captured either way.

### Stopping at a fixed time instead

Set `KASE_COLLECT_UNTIL=HH:MM` to have the collectors stop themselves at a
local wall-clock time:

```cmd
set KASE_COLLECT_UNTIL=18:00
tools\collector\collect-session.cmd HSBK.KZ
```

It is read as **local machine time**, so the machine's clock must be set to the
timezone you mean. The collectors stop *themselves* rather than being killed,
which matters: a killed process never writes `finished_at`, leaving the session
indistinguishable from a crash when you later look for gaps.

## Scheduled task (Windows)

Start the collector at logon so it comes back after a reboot. Review the
command before running it — it creates a persistent scheduled task on your
machine:

```cmd
schtasks /Create /TN "KASE Pilot collector" /SC ONLOGON ^
  /TR "cmd /c \"D:\KASE-Pilot\tools\collector\collect-session.cmd HSBK.KZ CCBN.KZ ASBN.KZ\""
```

Adjust the path and symbols to taste. Nothing stops it on a schedule; it runs
until the machine restarts or you stop it yourself.

To run without a visible window and even when you are not logged in, use
`/SC ONSTART` with `/RU` and `/RP` so the task has its own credentials, or set
"Run whether user is logged on or not" in the Task Scheduler UI. Be aware that
stores the account password in Windows Credential Manager.

Useful follow-ups:

```cmd
schtasks /Query  /TN "KASE Pilot collector" /V /FO LIST
schtasks /Run    /TN "KASE Pilot collector"
schtasks /End    /TN "KASE Pilot collector"
schtasks /Delete /TN "KASE Pilot collector" /F
```

Note that `schtasks /End` kills the process rather than letting it finish, so
the collection session it interrupts will have no `finished_at` — expected when
you stop a continuous collector this way, but it does mean the session cannot
later be told apart from a crash.

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
