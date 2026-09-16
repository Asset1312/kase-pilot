#!/bin/bash
# Setup script for running Bybit Standalone Bot on Android (Termux)
echo "=== Setting up Bybit Standalone Bot on Termux ==="
pkg update -y
pkg install python git termux-tools -y
pip install requests python-dotenv

# Prevent Android from putting CPU to sleep
termux-wake-lock

echo ""
echo "=== Installation finished! ==="
echo "To start the bot, run:"
echo "python bybit_standalone_bot.py"
