@echo off
REM Start quote and order-book collection for one or more instruments.
REM
REM Each collector runs in its own console window and keeps running until you
REM close it or press Ctrl+C. Quotes share a single window (one subscription
REM covers several symbols); the order book gets one window per symbol,
REM because the broker's market-depth subscription is per-instrument.
REM
REM Usage:
REM   collect-all.cmd HSBK.KZ
REM   collect-all.cmd HSBK.KZ KSPI.KZ CCBN.KZ
REM
REM For unattended collection use scheduled tasks instead - see README.md.

setlocal

if "%~1"=="" (
    echo Usage: collect-all.cmd SYMBOL [SYMBOL ...] 1>&2
    exit /b 2
)

REM Fail before opening any windows, otherwise the error flashes past in a
REM child window that the user may not be looking at.
if "%TRADERNET_PUBLIC_KEY%"=="" (
    echo TRADERNET_PUBLIC_KEY is not set 1>&2
    exit /b 1
)
if "%TRADERNET_PRIVATE_KEY%"=="" (
    echo TRADERNET_PRIVATE_KEY is not set 1>&2
    exit /b 1
)

set "COLLECTOR_DIR=%~dp0"

echo Starting quote collection for: %*
start "KASE Pilot quotes" cmd /k ""%COLLECTOR_DIR%collect-quotes.cmd" %*"

for %%S in (%*) do (
    echo Starting order-book collection for: %%S
    start "KASE Pilot order book %%S" cmd /k ""%COLLECTOR_DIR%collect-orderbook.cmd" %%S"
)

echo.
echo Collectors launched in separate windows.
echo Close a window or press Ctrl+C in it to stop that collector.

endlocal
