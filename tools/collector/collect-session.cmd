@echo off
REM Collect both market streams continuously.
REM
REM Runs until stopped. Set KASE_COLLECT_UNTIL=HH:MM to make the collectors
REM stop themselves at a local wall-clock time instead; they then exit cleanly
REM and each collection session is recorded as finished in the database, unlike
REM a killed process, which leaves finished_at empty and looks like a crash
REM when you later go looking for gaps.
REM
REM Both streams are collected in this one process tree, without opening
REM console windows, so it works under a scheduled task running hidden.
REM
REM Usage:
REM   collect-session.cmd HSBK.KZ
REM   collect-session.cmd HSBK.KZ KSPI.KZ

setlocal

if "%~1"=="" (
    echo Usage: collect-session.cmd SYMBOL [SYMBOL ...] 1>&2
    exit /b 2
)

if "%TRADERNET_PUBLIC_KEY%"=="" (
    echo TRADERNET_PUBLIC_KEY is not set 1>&2
    exit /b 1
)
if "%TRADERNET_PRIVATE_KEY%"=="" (
    echo TRADERNET_PRIVATE_KEY is not set 1>&2
    exit /b 1
)

REM Anything still holding the log files would make the new collectors fail
REM with four unexplained "file is in use" lines. Check for the wrappers too,
REM not just the collectors: a wrapper can outlive the collector it started
REM and keep the log open on its own.
call :collector_running && (
    echo Collectors are already running, or a previous run left a wrapper 1>&2
    echo behind that still holds the log files. Check, then stop them: 1>&2
    echo   tools\collector\collector-status.cmd 1>&2
    echo   tools\collector\stop-collectors.cmd 1>&2
    exit /b 1
)

set "COLLECTOR_DIR=%~dp0"
for %%I in ("%~dp0..\..") do set "PROJECT_DIR=%%~fI"
set "LOG_DIR=%PROJECT_DIR%\data\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if defined KASE_COLLECT_UNTIL (
    echo Collecting until %KASE_COLLECT_UNTIL% local time; logs in %LOG_DIR%
) else (
    echo Collecting continuously; logs in %LOG_DIR%
)

REM /b keeps these in the same console (no new windows), so a hidden scheduled
REM task stays hidden. Each wrapper applies its own redirect, taking the target
REM from KASE_COLLECT_LOG - the child inherits the value set just before it is
REM started. Redirecting here instead would mean nesting quotes inside
REM `cmd /c "..."`, which cmd mis-parses and which silently sends every
REM collector's output to the wrong place.
REM `cmd /c` is spelled out because `start` otherwise launches a .cmd through
REM `cmd /K`, which keeps the wrapper alive after the collector exits. Those
REM survivors hold the log files open forever, so the next run fails with
REM "the file is in use" while nothing named kase-pilot is even running.
set "KASE_COLLECT_LOG=%LOG_DIR%\quotes.log"
start /b "" cmd /c "%COLLECTOR_DIR%collect-quotes.cmd" %*

for %%S in (%*) do (
    set "KASE_COLLECT_LOG=%LOG_DIR%\orderbook-%%S.log"
    call :start_orderbook "%%S"
)
goto :collectors_started

:start_orderbook
start /b "" cmd /c "%COLLECTOR_DIR%collect-orderbook.cmd" %~1
exit /b 0

REM Succeeds when collection is already under way. Callers use
REM `call :collector_running && (...)`.
REM
REM Two questions, because either alone misses a case. A running collector is
REM the ordinary case. A locked log file catches the awkward one: a wrapper
REM that outlived its collector still owns the handle, so nothing named
REM kase-pilot is running yet the next run would still fail to write.
:collector_running
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if not errorlevel 1 exit /b 0
if exist "%LOG_DIR%\quotes.log" (
    2>nul ( >>"%LOG_DIR%\quotes.log" call ) || exit /b 0
)
exit /b 1

:collectors_started

REM Stay alive while the collectors run, so a scheduled task reports the real
REM run duration instead of exiting immediately. Without KASE_COLLECT_UNTIL
REM this waits indefinitely, which is the point: the task stays "running" for
REM as long as collection does.
REM
REM ping rather than timeout or waitfor, both of which spin here. The
REM collectors started with `start /b` share this console's stdin, so timeout
REM fails instantly with "Input redirection is not supported"; waitfor survives
REM that but stops waiting once the tasklist pipe below has run. ping needs
REM neither stdin nor the console, so it is the only one that actually sleeps
REM on every pass. -n 61 is sixty one-second gaps.
:wait
ping -n 61 127.0.0.1 >nul
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if not errorlevel 1 goto wait

echo Collection stopped.

endlocal
