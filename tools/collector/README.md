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

## Collecting one trading session, hands-off

`collect-session.cmd` collects both streams and stops itself at a wall-clock
time, without opening console windows:

```cmd
set KASE_COLLECT_UNTIL=18:00
tools\collector\collect-session.cmd HSBK.KZ KSPI.KZ
```

`KASE_COLLECT_UNTIL` defaults to `18:00` and is read as **local machine
time** — so the machine's clock must actually be set to the timezone you mean.
Output goes to `data/logs/`, since nothing is watching a console.

The collectors stop *themselves* at that time rather than being killed. This
matters: a killed process never writes `finished_at`, so the session becomes
indistinguishable from a crash when you later look for gaps.

Note that the broker's own market status (`docs/API_NOTES.md` F-26) reports
KASE closing at 22:00, not 18:00. If 18:00 is the end of the main session
rather than of trading altogether, collecting until 18:00 leaves the rest of
the day uncollected.

## Scheduled task (Windows)

Start the session collector every weekday at the market open. Review the
command before running it — it creates a persistent scheduled task on your
machine:

```cmd
schtasks /Create /TN "KASE Pilot session" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 11:30 ^
  /TR "cmd /c \"D:\KASE-Pilot\tools\collector\collect-session.cmd HSBK.KZ\""
```

Adjust the path and symbols to taste. `/ST 11:30` is the machine's local time,
matching how `--until` is interpreted — both assume the machine's clock is set
to the timezone you actually mean.

No second task is needed to stop it: the collectors exit on their own at
`KASE_COLLECT_UNTIL` (18:00 unless you set it otherwise). If you set that
variable with `setx` it applies to scheduled runs too; setting it with `set` in
your own terminal does not.

To run without a visible window and even when you are not logged in, add
`/RU` and `/RP` so the task has its own credentials, or set "Run whether user
is logged on or not" in the Task Scheduler UI. Be aware that stores the account
password in Windows Credential Manager.

Useful follow-ups:

```cmd
schtasks /Query  /TN "KASE Pilot session" /V /FO LIST
schtasks /Run    /TN "KASE Pilot session"
schtasks /End    /TN "KASE Pilot session"
schtasks /Delete /TN "KASE Pilot session" /F
```

Note that `schtasks /End` kills the process rather than letting it finish, so
the collection session it interrupts will have no `finished_at` — use it to
stop a stuck run, not as the normal way to end a day.

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
