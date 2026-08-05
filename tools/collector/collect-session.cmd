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

REM Collectors already running would fight the new ones over the same log
REM files, and the only symptom would be four "file is in use" lines with no
REM hint of the cause. Refuse instead, and say what to do about it.
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if not errorlevel 1 (
    echo Collectors are already running. 1>&2
    echo Stop them first, or leave them be - they are still collecting. 1>&2
    echo   tasklist /fi "imagename eq kase-pilot.exe" 1>&2
    echo   taskkill /im kase-pilot.exe 1>&2
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
set "KASE_COLLECT_LOG=%LOG_DIR%\quotes.log"
start /b "" "%COLLECTOR_DIR%collect-quotes.cmd" %*

for %%S in (%*) do (
    set "KASE_COLLECT_LOG=%LOG_DIR%\orderbook-%%S.log"
    call :start_orderbook "%%S"
)
goto :collectors_started

:start_orderbook
start /b "" "%COLLECTOR_DIR%collect-orderbook.cmd" %~1
exit /b 0

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
