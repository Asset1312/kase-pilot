@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo ========================================================
echo   Bybit Kazakhstan: Desktop Node (Smart Step)
echo   Mode: Standalone (No Telegram)
echo   Hours: 08:00 - 17:30 (Astana, UTC+5)
echo ========================================================
echo.
echo Local Web Dashboard: http://localhost:8080/
echo.

"%PYTHON_EXE%" bybit_standalone_bot.py --mode=desktop --no-telegram

pause