@echo off
REM Background quote collector for KASE Pilot.
REM
REM Reads credentials from the machine/user environment (set them once with
REM setx, or configure them on the scheduled task itself), then streams quotes
REM with --save and --reconnect so a dropped connection resumes on its own.
REM
REM Usage:
REM   collect-quotes.cmd HSBK.KZ KSPI.KZ
REM
REM stdout carries the raw JSON messages; stderr carries reconnection notices.
REM Redirect both when running unattended - see tools/collector/README.md.

setlocal

if "%~1"=="" (
    echo Usage: collect-quotes.cmd SYMBOL [SYMBOL ...] 1>&2
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

set "UNTIL_ARG="
if defined KASE_COLLECT_UNTIL set "UNTIL_ARG=--until %KASE_COLLECT_UNTIL%"

REM Redirection lives here rather than in a caller's `cmd /c "..."`, because
REM nesting quotes inside cmd /c breaks the redirect target.
if defined KASE_COLLECT_LOG (
    kase-pilot stream-quotes %* --save --reconnect %UNTIL_ARG% >> "%KASE_COLLECT_LOG%" 2>&1
) else (
    kase-pilot stream-quotes %* --save --reconnect %UNTIL_ARG%
)

endlocal
