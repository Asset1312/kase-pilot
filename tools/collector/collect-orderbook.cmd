@echo off
REM Background order-book collector for KASE Pilot.
REM
REM One instrument per process - the broker's market-depth subscription takes a
REM single symbol. Run several scheduled tasks to cover several instruments.
REM
REM Usage:
REM   collect-orderbook.cmd HSBK.KZ

setlocal

if "%~1"=="" (
    echo Usage: collect-orderbook.cmd SYMBOL 1>&2
    exit /b 2
)
if not "%~2"=="" (
    echo collect-orderbook.cmd accepts exactly one symbol 1>&2
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
    kase-pilot stream-orderbook %1 --save --reconnect %UNTIL_ARG% >> "%KASE_COLLECT_LOG%" 2>&1
) else (
    kase-pilot stream-orderbook %1 --save --reconnect %UNTIL_ARG%
)

endlocal
