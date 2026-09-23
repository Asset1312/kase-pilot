import io
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bybit_standalone_bot import (
    StandaloneBybitBot,
    SimpleDashboardHandler,
    compute_trade_analytics,
    TRAILING_ACTIVATION_PCT,
)


class TestRocketAndTradeAnalytics(unittest.TestCase):
    def test_compute_trade_analytics(self):
        # 2 executions: 1 Buy and 1 Sell
        execs = [
            {
                "execTime": "1790046423000",
                "side": "Buy",
                "execPrice": "1.0443",
                "execQty": "10.10",
                "execValue": "10.54743",
                "execFee": "0.0101",
                "feeCurrency": "SUI",
            },
            {
                "execTime": "1790038500000",
                "side": "Sell",
                "execPrice": "1.0650",
                "execQty": "5.58",
                "execValue": "5.9427",
                "execFee": "0.005",
                "feeCurrency": "USDT",
            },
        ]
        res = compute_trade_analytics(execs)
        self.assertEqual(res["total_trades"], 2)
        self.assertEqual(res["buys_count"], 1)
        self.assertEqual(res["sells_count"], 1)
        self.assertAlmostEqual(res["total_volume"], 16.49, places=2)
        self.assertEqual(len(res["recent_trades"]), 2)
        self.assertIn("hourly", res)
        self.assertIn("dow", res)
        self.assertEqual(len(res["hourly"]), 24)

    def test_rocket_target_math(self):
        entry_price = 1.0529
        expected_target = round(entry_price * (1.0 + TRAILING_ACTIVATION_PCT), 4)
        self.assertEqual(expected_target, 1.0603)

        cur_price = 1.0400
        distance_pct = round(((expected_target - cur_price) / cur_price) * 100, 2)
        self.assertGreater(distance_pct, 0)
        self.assertEqual(distance_pct, 1.95)

    def test_dashboard_renders_rocket_and_analytics(self):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
        bot.stats["tokens"]["SUIUSDT"] = {
            "symbol": "SUIUSDT",
            "name": "Sui",
            "base_coin": "SUI",
            "badge_color": "#38bdf8",
            "mode": "ACTIVE",
            "price": 1.0400,
            "free_coin": 15.68,
            "locked_coin": 0.0,
            "holding_value_usd": 16.31,
            "entry_price": 1.0529,
            "rocket_target_price": 1.0634,
            "rocket_distance_pct": 2.25,
            "current_gain_pct": -1.23,
            "trailing_active": False,
            "trailing_peak_price": 0.0,
            "trailing_stop_price": 0.0,
            "trailing_floor_price": 0.0,
            "completed_cycles": 9,
            "net_profit_usd": 0.4561,
            "tp_mode": "🚀 Rocket Rider (Цель: +1.00%)",
            "position_age_hours": 0.5,
            "step1_discount_pct": 1.1,
            "step2_discount_pct": 2.2,
            "step3_discount_pct": 4.8,
            "vol_multiplier": 2.0,
            "volatility_regime": "STORM",
            "range_15m_pct": 1.8,
            "chg_1m_pct": 0.0,
            "cooldown_active": False,
            "cooldown_reason": "",
        }
        bot.stats["trade_analytics"] = {
            "total_trades": 100,
            "total_volume": 956.06,
            "buys_count": 50,
            "sells_count": 50,
            "recent_trades": [
                {
                    "time": "22.09 08:07",
                    "side": "Buy",
                    "price": 1.0443,
                    "qty": 10.1,
                    "val": 10.55,
                    "fee": 0.0101,
                    "fee_coin": "SUI",
                }
            ],
            "hourly": {h: {"count": 4, "volume": 40.0, "buys": 2, "sells": 2} for h in range(24)},
            "dow": {d: {"count": 14, "volume": 140.0} for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]},
        }

        request_text = "GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
        rfile = io.BytesIO(request_text.encode("utf-8"))
        wfile = io.BytesIO()

        SimpleDashboardHandler.bot_instance = bot
        handler = SimpleDashboardHandler.__new__(SimpleDashboardHandler)
        handler.rfile = rfile
        handler.wfile = wfile
        handler.path = "/"
        handler.command = "GET"
        handler.requestline = "GET / HTTP/1.1"
        handler.request_version = "HTTP/1.1"
        handler.close_connection = True
        handler.headers = {}
        handler.log_message = MagicMock()

        handler.do_GET()
        output = wfile.getvalue().decode("utf-8")

        # Check Rocket Target elements
        self.assertIn("1.0634", output)
        self.assertIn("1.0529", output)
        self.assertIn("Ждем активацию РАКЕТЫ", output)
        self.assertIn("Прогресс", output)

        # Check Trade Analytics elements
        self.assertIn("Статистика торгов", output)
        self.assertIn("956.06 USDT", output)
        self.assertIn("Распределение по дням недели", output)
        self.assertIn("Распределение по часам", output)
        self.assertIn("22.09 08:07", output)


if __name__ == "__main__":
    unittest.main()
