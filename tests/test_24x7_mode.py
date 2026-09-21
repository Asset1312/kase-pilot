import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "tradernet-cloud-bot")))

import bybit_standalone_bot
from bybit_standalone_bot import StandaloneBybitBot, init_cluster_role

class Test24x7Mode(unittest.TestCase):
    def test_init_24x7_profile(self):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        self.assertTrue(bot.is_24x7)
        self.assertEqual(bot.stats["profile"], "DESKTOP / 24x7 SMART-STEP")
        self.assertTrue(bot.stats["is_24x7"])

    @patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=False)
    def test_init_cluster_role_24x7_outside_hours(self, mock_win):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        init_cluster_role(bot)
        self.assertTrue(bot.is_active_controller)
        self.assertEqual(bot.role, "ACTIVE_CONTROLLER")

    @patch("bybit_standalone_bot.is_desktop_schedule_window", return_value=False)
    def test_regular_desktop_outside_hours_is_passive(self, mock_win):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=False)
        init_cluster_role(bot)
        self.assertFalse(bot.is_active_controller)
        self.assertEqual(bot.role, "PASSIVE_OBSERVER")

if __name__ == "__main__":
    unittest.main()
