"""Unit tests for MomentumBreakoutController (Squeeze Explosion & Impulse Scalper)."""
import pytest
from unittest.mock import MagicMock
from bybit_standalone_bot import (
    MomentumBreakoutController,
    BreakoutState,
    BREAKOUT_BUDGET_USD,
    BREAKOUT_LOOKBACK_BARS,
    BREAKOUT_VOLUME_FACTOR,
    BREAKOUT_STOP_LOSS_PCT,
    BREAKOUT_ROCKET_ACTIVATION_PCT,
)


def test_breakout_initialization():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25)
    assert controller.symbol == "SUIUSDT"
    assert controller.budget_usd == 5.25
    assert controller.state.status == "IDLE"
    assert controller.state.allocated_usd == 5.25
    d = controller.to_dict()
    assert d["status"] == "IDLE"
    assert d["allocated_usd"] == 5.25


def test_breakout_triggers_on_price_and_volume_breakout():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25, volume_factor=2.0)
    client_mock = MagicMock()
    client_mock.create_market_order.return_value = {"retCode": 0, "result": {"orderId": "brk_1"}}

    # Build 15 completed candles where resistance is 0.9500 and avg volume is 10,000
    # Candle format: [startTime, open, high, low, close, volume, turnover]
    klines = [
        # Forming candle (index 0) has volume spike of 25,000 (2.5x avg)
        ["100", "0.9500", "0.9560", "0.9490", "0.9550", "25000.0", "23000"],
    ]
    for i in range(1, 16):
        klines.append([str(100 - i * 60), "0.9450", "0.9500", "0.9420", "0.9460", "10000.0", "9400"])

    cur_price = 0.9520  # Above resistance (0.9500)
    avail_usdt = 10.00

    res = controller.tick(
        client=client_mock,
        cur_price=cur_price,
        avail_usdt=avail_usdt,
        free_qty=0.0,
        lead_lag_status="CLEAR",
        klines=klines,
        obi=0.15,
        price_decimals=4,
        qty_decimals=2,
    )

    assert res is not None
    assert res["action"] == "BREAKOUT_ENTERED"
    assert controller.state.status == "IN_FLIGHT"
    assert controller.state.entry_price == cur_price
    assert controller.state.position_qty > 0
    client_mock.create_market_order.assert_called_once_with("SUIUSDT", "Buy", controller.state.position_qty)


def test_breakout_ignores_when_volume_not_confirmed():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25, volume_factor=2.0)
    client_mock = MagicMock()

    # Forming candle has low volume (8,000 vs 10,000 avg -> ratio 0.8x < 2.0x)
    klines = [
        ["100", "0.9500", "0.9560", "0.9490", "0.9550", "8000.0", "7600"],
    ]
    for i in range(1, 16):
        klines.append([str(100 - i * 60), "0.9450", "0.9500", "0.9420", "0.9460", "10000.0", "9400"])

    cur_price = 0.9520  # Above resistance, but no volume
    res = controller.tick(
        client=client_mock,
        cur_price=cur_price,
        avail_usdt=10.00,
        free_qty=0.0,
        lead_lag_status="CLEAR",
        klines=klines,
        obi=0.10,
    )

    assert res is None
    assert controller.state.status == "ARMED"  # Price broke out, but waiting for volume confirmation
    client_mock.create_market_order.assert_not_called()


def test_breakout_blocks_on_negative_obi():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25, volume_factor=2.0)
    client_mock = MagicMock()

    # Price broke out, volume is huge (30,000), but OBI is severely negative (-0.30 < -0.15)
    klines = [
        ["100", "0.9500", "0.9560", "0.9490", "0.9550", "30000.0", "28500"],
    ]
    for i in range(1, 16):
        klines.append([str(100 - i * 60), "0.9450", "0.9500", "0.9420", "0.9460", "10000.0", "9400"])

    cur_price = 0.9520
    res = controller.tick(
        client=client_mock,
        cur_price=cur_price,
        avail_usdt=10.00,
        free_qty=0.0,
        lead_lag_status="CLEAR",
        klines=klines,
        obi=-0.30,  # Massive sell wall overhead!
    )

    assert res is None
    client_mock.create_market_order.assert_not_called()


def test_breakout_blocks_on_btc_crash():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25)
    client_mock = MagicMock()

    klines = [["100", "0.9500", "0.9560", "0.9490", "0.9550", "30000.0", "28500"]]
    for i in range(1, 16):
        klines.append([str(100 - i * 60), "0.9450", "0.9500", "0.9420", "0.9460", "10000.0", "9400"])

    res = controller.tick(
        client=client_mock,
        cur_price=0.9520,
        avail_usdt=10.00,
        free_qty=0.0,
        lead_lag_status="CRASH",  # Systemic market drop
        klines=klines,
        obi=0.10,
    )

    assert res is None
    assert controller.state.status == "IDLE"
    client_mock.create_market_order.assert_not_called()


def test_breakout_hard_stop_loss():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25, stop_loss_pct=0.0120)
    controller.state.status = "IN_FLIGHT"
    controller.state.entry_price = 1.0000
    controller.state.position_qty = 5.25

    client_mock = MagicMock()
    client_mock.create_market_order.return_value = {"retCode": 0}

    # Price dumps to 0.9850 (-1.50% <= -1.20% stop loss)
    res = controller.tick(
        client=client_mock,
        cur_price=0.9850,
        avail_usdt=5.00,
        free_qty=5.25,
        lead_lag_status="CLEAR",
        klines=[],
    )

    assert res is not None
    assert res["action"] == "STOP_LOSS"
    assert controller.state.status == "COOLDOWN"
    client_mock.create_market_order.assert_called_once_with("SUIUSDT", "Sell", 5.25)


def test_breakout_trailing_rocket_exit():
    controller = MomentumBreakoutController(
        symbol="SUIUSDT",
        budget_usd=5.25,
        rocket_activation_pct=0.0090,  # +0.90% activates
        rocket_callback_pct=0.0035,    # 0.35% pullback triggers exit
        rocket_floor_pct=0.0065,       # +0.65% floor
    )
    controller.state.status = "IN_FLIGHT"
    controller.state.entry_price = 1.0000
    controller.state.position_qty = 5.25

    client_mock = MagicMock()
    client_mock.create_market_order.return_value = {"retCode": 0}

    # 1. Price rallies to 1.0120 (+1.20% > 0.90%) -> Rocket Armed!
    res1 = controller.tick(
        client=client_mock,
        cur_price=1.0120,
        avail_usdt=5.00,
        free_qty=5.25,
        lead_lag_status="CLEAR",
        klines=[],
        price_decimals=4,
    )
    assert res1 is not None
    assert res1["action"] == "ROCKET_ARMED"
    assert controller.state.trailing_active is True
    assert controller.state.peak_price == 1.0120
    # Stop price = max(1.0120 * (1 - 0.0035), 1.0065) = max(1.0085, 1.0065) = 1.0085
    assert controller.state.stop_price == 1.0085

    # 2. Price pulls back to 1.0080 (<= stop 1.0085) -> Eject and lock in profit!
    res2 = controller.tick(
        client=client_mock,
        cur_price=1.0080,
        avail_usdt=5.00,
        free_qty=5.25,
        lead_lag_status="CLEAR",
        klines=[],
        price_decimals=4,
    )
    assert res2 is not None
    assert res2["action"] == "PROFIT_EXIT"
    assert controller.state.status == "COOLDOWN"
    assert controller.state.total_profit_usd > 0
    client_mock.create_market_order.assert_called_once_with("SUIUSDT", "Sell", 5.25)


def test_breakout_reconciles_when_coins_closed_externally():
    controller = MomentumBreakoutController(symbol="SUIUSDT", budget_usd=5.25)
    controller.state.status = "IN_FLIGHT"
    controller.state.entry_price = 0.9674
    controller.state.position_qty = 5.60

    client_mock = MagicMock()
    # Coins are no longer on balance (free_qty <= 0.05)
    res = controller.tick(
        client=client_mock,
        cur_price=0.9670,
        avail_usdt=10.0,
        free_qty=0.0,
        lead_lag_status="CLEAR",
        klines=[],
    )

    assert res is not None
    assert res["action"] == "EXTERNAL_CLOSE"
    assert controller.state.status == "IDLE"
    assert controller.state.position_qty == 0.0
    assert controller.state.entry_price == 0.0
    client_mock.create_market_order.assert_not_called()

