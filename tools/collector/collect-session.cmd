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

set "PROJECT_DIR=%~dp0..\.."
set "LOG_DIR=%PROJECT_DIR%\data\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

if defined KASE_COLLECT_UNTIL (
    set "UNTIL_ARG=--until %KASE_COLLECT_UNTIL%"
    echo Collecting until %KASE_COLLECT_UNTIL% local time; logs in %LOG_DIR%
) else (
    set "UNTIL_ARG="
    echo Collecting continuously; logs in %LOG_DIR%
)

REM /b keeps these in the same console (no new windows), so a hidden scheduled
REM task stays hidden. Output goes to logs, since nobody is watching a console.
start /b "" cmd /c "kase-pilot stream-quotes %* --save --reconnect %UNTIL_ARG% >> "%LOG_DIR%\quotes.log" 2>&1"

for %%S in (%*) do (
    start /b "" cmd /c "kase-pilot stream-orderbook %%S --save --reconnect %UNTIL_ARG% >> "%LOG_DIR%\orderbook-%%S.log" 2>&1"
)

REM Stay alive while the collectors run, so a scheduled task reports the real
REM run duration instead of exiting immediately. Without KASE_COLLECT_UNTIL
REM this waits indefinitely, which is the point: the task stays "running" for
REM as long as collection does.
:wait
timeout /t 60 /nobreak >nul
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if not errorlevel 1 goto wait

echo Collection stopped.

endlocal
