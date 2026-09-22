import pytest
from unittest.mock import MagicMock, patch
from bybit_standalone_bot import (
    StandaloneBybitBot,
    SCALE_OUT_TRIGGER_GAIN_PCT,
    PRIMARY_SYMBOL,
)


def test_scale_out_triggers_on_bounce_with_large_holding():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()

        # Simulate large holding (31.67 SUI @ $1.0351, holding_val ~ $32.7 > $24.00)
        # Entry price = 1.0000, current price = 1.0060 (+0.60% > +0.50% trigger)
        bot.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "available_usdt": 15.00,
            "locked_usdt": 0.0,
            "total_usd": 46.85,
            "coins": {
                "SUI": {"free": 31.67, "locked": 0.0},
                "NEAR": {"free": 0.0, "locked": 0.0},
                "AVAX": {"free": 0.0, "locked": 0.0},
            },
        }
        bot.client._request.side_effect = lambda method, endpoint, params=None, data=None: (
            {"retCode": 0, "result": {"list": [{"lastPrice": "1.0060"}]}}
            if endpoint == "/v5/market/tickers"
            else {"retCode": 0, "result": {}}
        )
        # Fake execution history so recent_buys has VWAP $1.0000
        bot.client.get_execution_history.return_value = [
            {"execPrice": "1.0000", "execQty": "31.67", "side": "Buy", "execTime": "1790070000000"}
        ]
        bot.client.get_open_orders.return_value = []
        bot.client.create_market_order.return_value = {"retCode": 0, "result": {"orderId": "SO_SELL_1"}}

        bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))
        bot.guard.lead_lag_status = "CLEAR"
        bot.guard.gate_step1_open = True
        bot.guard.dca_protection_active = False

        bot.step()

        # Verify create_market_order was called with "Sell" and ~48% of free qty (~15.20 SUI)
        market_sells = [
            c for c in bot.client.create_market_order.call_args_list
            if len(c[0]) > 1 and c[0][1] == "Sell"
        ]
        assert len(market_sells) == 1, f"Expected 1 partial scale-out market sell, got {market_sells}"
        sold_qty = market_sells[0][0][2]
        assert 14.0 <= sold_qty <= 16.0, f"Expected ~15 SUI sold, got {sold_qty}"
        assert bot.last_scale_out_ts[PRIMARY_SYMBOL] > 0


def test_scale_out_does_not_trigger_when_gain_is_low():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()

        # Large holding, but current price only +0.20% (below +0.50%)
        bot.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "available_usdt": 15.00,
            "locked_usdt": 0.0,
            "total_usd": 46.85,
            "coins": {
                "SUI": {"free": 31.67, "locked": 0.0},
                "NEAR": {"free": 0.0, "locked": 0.0},
                "AVAX": {"free": 0.0, "locked": 0.0},
            },
        }
        bot.client._request.side_effect = lambda method, endpoint, params=None, data=None: (
            {"retCode": 0, "result": {"list": [{"lastPrice": "1.0020"}]}}
            if endpoint == "/v5/market/tickers"
            else {"retCode": 0, "result": {}}
        )
        bot.recent_buys[PRIMARY_SYMBOL] = [
            {"execPrice": "1.0000", "execQty": "31.67", "side": "Buy"}
        ]
        bot.client.get_open_orders.return_value = []

        bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))
        bot.guard.lead_lag_status = "CLEAR"
        bot.guard.gate_step1_open = True
        bot.guard.dca_protection_active = False

        bot.step()

        market_sells = [
            c for c in bot.client.create_market_order.call_args_list
            if len(c[0]) > 1 and c[0][1] == "Sell"
        ]
        assert len(market_sells) == 0, "Scale-out should not fire when gain < +0.50%"


def test_scale_out_does_not_trigger_on_small_position():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()

        # Small holding (only 5 SUI @ $1.00 = $5.00 < $24.00)
        bot.client.get_wallet_balance.return_value = {
            "retCode": 0,
            "available_usdt": 20.00,
            "locked_usdt": 0.0,
            "total_usd": 25.00,
            "coins": {
                "SUI": {"free": 5.0, "locked": 0.0},
                "NEAR": {"free": 0.0, "locked": 0.0},
                "AVAX": {"free": 0.0, "locked": 0.0},
            },
        }
        bot.client._request.side_effect = lambda method, endpoint, params=None, data=None: (
            {"retCode": 0, "result": {"list": [{"lastPrice": "1.0080"}]}}
            if endpoint == "/v5/market/tickers"
            else {"retCode": 0, "result": {}}
        )
        bot.recent_buys[PRIMARY_SYMBOL] = [
            {"execPrice": "1.0000", "execQty": "5.0", "side": "Buy"}
        ]
        bot.client.get_open_orders.return_value = []

        bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))
        bot.guard.lead_lag_status = "CLEAR"
        bot.guard.gate_step1_open = True
        bot.guard.dca_protection_active = False

        bot.step()

        market_sells = [
            c for c in bot.client.create_market_order.call_args_list
            if len(c[0]) > 1 and c[0][1] == "Sell"
        ]
        assert len(market_sells) == 0, "Scale-out should not fire on small initial position"
