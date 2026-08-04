@echo off
REM Collect one KASE trading session, then exit cleanly.
REM
REM Intended to be started by Task Scheduler at the session open. The
REM collectors stop themselves at KASE_COLLECT_UNTIL rather than being killed,
REM so each collection session is recorded as finished in the database. A
REM killed process leaves finished_at empty, which is indistinguishable from a
REM crash when you later look for gaps in the data.
REM
REM Both streams are collected in this one process tree, without opening
REM console windows, so it works under a scheduled task running hidden.
REM
REM Usage:
REM   collect-session.cmd HSBK.KZ
REM   collect-session.cmd HSBK.KZ KSPI.KZ
REM
REM Stop time defaults to 18:00 local; override with KASE_COLLECT_UNTIL.

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

if not defined KASE_COLLECT_UNTIL set "KASE_COLLECT_UNTIL=18:00"

set "PROJECT_DIR=%~dp0..\.."
set "LOG_DIR=%PROJECT_DIR%\data\logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Collecting until %KASE_COLLECT_UNTIL% local time; logs in %LOG_DIR%

REM /b keeps these in the same console (no new windows), so a hidden scheduled
REM task stays hidden. Output goes to logs, since nobody is watching a console.
start /b "" cmd /c "kase-pilot stream-quotes %* --save --reconnect --until %KASE_COLLECT_UNTIL% >> "%LOG_DIR%\quotes.log" 2>&1"

for %%S in (%*) do (
    start /b "" cmd /c "kase-pilot stream-orderbook %%S --save --reconnect --until %KASE_COLLECT_UNTIL% >> "%LOG_DIR%\orderbook-%%S.log" 2>&1"
)

REM Wait for the collectors to finish so the scheduled task reports the real
REM run duration instead of exiting immediately.
:wait
timeout /t 60 /nobreak >nul
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if not errorlevel 1 goto wait

echo Session finished.

endlocal
