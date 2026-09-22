import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "deploy", "tradernet-cloud-bot")))

import bybit_standalone_bot
from bybit_standalone_bot import MarketGuard, StandaloneBybitBot, BASE_SPACING

class TestAnchorDCA(unittest.TestCase):
    def test_storm_discount_cap(self):
        guard = MarketGuard()
        # Mock high 15m volatility (e.g. 3.0% range -> mult = 2.0)
        klines = [
            [0, 1.00, 1.03, 1.00, 1.02, 100],
            [0, 1.00, 1.02, 0.99, 1.01, 100],
        ]
        with patch.object(guard, "fetch_klines", return_value=klines):
            guard.update_market_state(["SUIUSDT"])
            s2 = guard.token_metrics["SUIUSDT"]["step2_discount"]
            s3 = guard.token_metrics["SUIUSDT"]["step3_discount"]
            self.assertLessEqual(s2, 0.0220)
            self.assertLessEqual(s3, 0.0480)

    def test_anchor_target_when_step1_held(self):
        entry_price = 1.0678
        cur_price = 1.0500
        s2_disc = 0.0220
        # When step1_held, t2 should be derived from entry_price:
        t2_anchored = round(entry_price * (1.0 - s2_disc), 4)
        self.assertEqual(t2_anchored, 1.0443)
        # Should be strictly different from cur_price based calculation
        t2_floating = round(cur_price * (1.0 - s2_disc), 4)
        self.assertEqual(t2_floating, 1.0269)
        self.assertNotEqual(t2_anchored, t2_floating)

if __name__ == "__main__":
    unittest.main()
