#!/bin/bash
# ========================================================
#   Bybit Kazakhstan: Запуск бота на телефоне (Termux)
# ========================================================

# Защита от засыпания процессора Android
if command -v termux-wake-lock >/dev/null 2>&1; then
    termux-wake-lock
fi

# Переход в директорию скрипта
cd "$(dirname "$0")"

echo "========================================================"
echo "  📱 Bybit Казахстан: Мобильный узел (STORM x2.0)"
echo "  Окно работы: 17:30 - 08:00 (Вечер / Ночь / Выходные)"
echo "========================================================"
echo ""

# Автоматическое обновление из GitHub перед запуском
echo "🔄 Проверка обновлений (git pull)..."
git pull --rebase || true
echo ""

echo "🚀 Запуск Bybit Mobile Bot..."
python bybit_standalone_bot.py --mode=mobile