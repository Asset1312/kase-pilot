@echo off
REM Stop every collector and every wrapper left behind by one.
REM
REM `taskkill /im kase-pilot.exe` alone is not enough: the cmd.exe wrappers
REM that started the collectors can outlive them and keep the log files open,
REM which makes the next run fail with "the file is in use" while nothing
REM named kase-pilot is running.
REM
REM Note that killing a collector is not a clean stop: the collection session
REM never records finished_at, so it stays indistinguishable from a crash when
REM you later look for gaps. Use KASE_COLLECT_UNTIL for a clean scheduled stop.

setlocal

echo Stopping collectors...
taskkill /im kase-pilot.exe /f >nul 2>&1
if errorlevel 1 (
    echo   no kase-pilot process was running
) else (
    echo   collectors stopped
)

set "STOPPED_WRAPPERS=0"
for /f "skip=1 tokens=1" %%P in (
    'wmic process where "name='cmd.exe' and ^(commandline like '%%collect-quotes.cmd%%' or commandline like '%%collect-orderbook.cmd%%'^)" get processid 2^>nul'
) do (
    taskkill /pid %%P /f >nul 2>&1
    if not errorlevel 1 set /a STOPPED_WRAPPERS+=1
)
echo   wrappers stopped: %STOPPED_WRAPPERS%

endlocal
