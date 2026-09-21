@echo off
chcp 65001 >nul
title Bybit Micro-Fund: Desktop Node (Smart Step)
cd /d "%~dp0\.."

set PYTHON_EXE=.venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
    set PYTHON_EXE=python
)

echo ========================================================
echo   Bybit Казахстан: Рабочий профиль DESKTOP
echo   Режим: Smart Step (Асимметричная сетка + буфер $10)
echo   Окно работы: 08:00 - 17:30 (Астана, UTC+5)
echo ========================================================
echo.
echo Локальный веб-дашборд: http://localhost:8080/
echo.

"%PYTHON_EXE%" bybit_standalone_bot.py --mode=desktop --no-telegram
pause
