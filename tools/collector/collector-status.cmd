@echo off
REM Show whether collection is actually running, and what the database holds.
REM
REM A dead collector looks exactly like a quiet market, so this reports the
REM processes, the wrappers that can outlive them, and the newest stored
REM message rather than leaving you to infer any of it.

setlocal

for %%I in ("%~dp0..\..") do set "PROJECT_DIR=%%~fI"

echo === collectors ===
tasklist /fi "imagename eq kase-pilot.exe" 2>nul | find /i "kase-pilot.exe" >nul
if errorlevel 1 (
    echo   none running
) else (
    tasklist /fi "imagename eq kase-pilot.exe" /nh
)

echo.
echo === wrappers (these keep log files open even without a collector) ===
wmic process where "name='cmd.exe' and (commandline like '%%collect-quotes.cmd%%' or commandline like '%%collect-orderbook.cmd%%')" get processid,creationdate 2>nul | find /i "." || echo   none

echo.
echo === database ===
python -c "import sqlite3;from datetime import datetime,UTC;c=sqlite3.connect('file:%PROJECT_DIR:\=/%/data/database/market.sqlite3?mode=ro',uri=True);print('  now UTC        :',datetime.now(UTC).isoformat()[:19]);[print(f'  {t:<15}: {n:>7} rows, last {l[:19] if l else None}') for t,(n,l) in ((t,list(c.execute(f'SELECT COUNT(*),MAX(received_at) FROM {t}'))[0]) for t in ('quote_messages','order_book_messages'))]" 2>nul || echo   could not read the database

endlocal
