@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo ========================================================
echo   Bybit Kazakhstan: Desktop Node (Smart Step)
echo   Mode: 24/7 Standalone (No Telegram)
echo   Hours: 24/7 All-Day ^& Night (Astana, UTC+5)
echo ========================================================
echo.
echo Local Web Dashboard: http://localhost:8080/
echo.

"%PYTHON_EXE%" bybit_standalone_bot.py --mode=desktop --no-telegram --24x7

pause