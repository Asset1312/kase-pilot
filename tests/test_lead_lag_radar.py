import pytest
from unittest.mock import MagicMock, patch
from bybit_standalone_bot import (
    StandaloneBybitBot,
    MarketGuard,
    BTC_1M_DUMP_THRESHOLD,
    BTC_3M_DUMP_THRESHOLD,
    BTC_1M_SLIDING_THRESHOLD,
    BTC_3M_SLIDING_THRESHOLD,
    PRIMARY_SYMBOL,
)


def test_market_guard_evaluate_btc_clear():
    guard = MarketGuard()
    # Mock BTC klines: small changes (stable)
    # [timestamp, open, high, low, close, volume, turnover]
    klines = [
        ["1000", "60000.0", "60050.0", "59980.0", "60010.0", "10", "600000"],
        ["940",  "59990.0", "60020.0", "59950.0", "60000.0", "10", "600000"],
        ["880",  "60000.0", "60010.0", "59980.0", "59990.0", "10", "600000"],
    ]
    eval_res = guard.evaluate_btc_lead_lag(klines)
    assert eval_res["status"] in ("CLEAR", "BULLISH")
    assert eval_res["gate_step1_open"] is True
    assert eval_res["dca_protection_active"] is False


def test_market_guard_evaluate_btc_sliding():
    guard = MarketGuard()
    # BTC 1m drop -0.20% (worse than -0.15% sliding threshold, but better than -0.35% dump threshold)
    # open 60000, close 59880 -> -120 / 60000 = -0.0020 (-0.20%)
    klines = [
        ["1000", "60000.0", "60010.0", "59850.0", "59880.0", "15", "900000"],
        ["940",  "60020.0", "60050.0", "59990.0", "60000.0", "10", "600000"],
        ["880",  "60000.0", "60030.0", "59980.0", "60020.0", "10", "600000"],
    ]
    eval_res = guard.evaluate_btc_lead_lag(klines)
    assert eval_res["status"] == "SLIDING"
    assert eval_res["gate_step1_open"] is False
    assert eval_res["dca_protection_active"] is True


def test_market_guard_evaluate_btc_crash():
    guard = MarketGuard()
    # BTC 1m flash dump -0.50% (worse than -0.35%)
    # open 60000, close 59700 -> -300 / 60000 = -0.0050 (-0.50%)
    klines = [
        ["1000", "60000.0", "60010.0", "59650.0", "59700.0", "30", "1800000"],
        ["940",  "60050.0", "60060.0", "59990.0", "60000.0", "10", "600000"],
        ["880",  "60000.0", "60020.0", "59980.0", "60050.0", "10", "600000"],
    ]
    eval_res = guard.evaluate_btc_lead_lag(klines)
    assert eval_res["status"] == "CRASH"
    assert eval_res["gate_step1_open"] is False
    assert eval_res["dca_protection_active"] is True


def test_step1_blocked_when_btc_sliding():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()

        bot.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "available_usdt": 25.00,
            "locked_usdt": 0.0,
            "total_usd": 25.00,
            "coins": {
                "SUI": {"free": 0.0, "locked": 0.0},
                "NEAR": {"free": 0.0, "locked": 0.0},
                "AVAX": {"free": 0.0, "locked": 0.0},
            },
        }
        bot.client._request.side_effect = lambda method, endpoint, params=None, data=None: (
            {"retCode": 0, "result": {"list": [{"lastPrice": "1.0000"}]}}
            if endpoint == "/v5/market/tickers"
            else {"retCode": 0, "result": {}}
        )
        bot.client.get_open_orders.return_value = []

        bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))
        bot.guard.lead_lag_status = "SLIDING"
        bot.guard.lead_lag_reason = "BTC 1m Sliding (-0.22%)"
        bot.guard.gate_step1_open = False
        bot.guard.dca_protection_active = True

        bot.step()

        buy_calls = [
            c for c in bot.client.create_limit_order.call_args_list
            if len(c[0]) > 1 and c[0][1] == "Buy" and "CANARY" not in str(c)
        ]
        assert len(buy_calls) == 0, f"Expected 0 regular buy orders placed during BTC SLIDING, got {buy_calls}"


def test_step1_allowed_when_btc_clear():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()

        bot.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "available_usdt": 25.00,
            "locked_usdt": 0.0,
            "total_usd": 25.00,
            "coins": {
                "SUI": {"free": 0.0, "locked": 0.0},
                "NEAR": {"free": 0.0, "locked": 0.0},
                "AVAX": {"free": 0.0, "locked": 0.0},
            },
        }
        bot.client._request.side_effect = lambda method, endpoint, params=None, data=None: (
            {"retCode": 0, "result": {"list": [{"lastPrice": "1.0000"}]}}
            if endpoint == "/v5/market/tickers"
            else {"retCode": 0, "result": {}}
        )
        bot.client.get_open_orders.return_value = []
        bot.client.create_limit_order.return_value = {"retCode": 0, "result": {"orderId": "ORD_123"}}

        bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))
        bot.guard.lead_lag_status = "CLEAR"
        bot.guard.gate_step1_open = True
        bot.guard.dca_protection_active = False

        bot.step()

        buy_calls = [
            c for c in bot.client.create_limit_order.call_args_list
            if len(c[0]) > 1 and c[0][1] == "Buy"
        ]
        assert len(buy_calls) >= 1, "Expected Step 1 buy order to be placed when Lead-Lag gate is CLEAR"
