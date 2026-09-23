"""Unit tests for the Flash Sniper (Crash Harvester / Wick Catcher) module with Rocket Rider."""
import pytest
from unittest.mock import MagicMock
from bybit_standalone_bot import (
    FlashSniperController,
    FlashSniperState,
    SNIPER_ORDER_LINK_PREFIX,
    SNIPER_BUDGET_USD,
    SNIPER_DIP_DEPTH_PCT,
    SNIPER_TP_PCT,
    SNIPER_USE_ROCKET,
    SNIPER_ROCKET_ACTIVATION_PCT,
    SNIPER_ROCKET_CALLBACK_PCT,
    SNIPER_ROCKET_FLOOR_PCT,
)


def test_flash_sniper_init():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25)
    assert sniper.symbol == "NEARUSDT"
    assert sniper.budget_usd == 5.25
    assert sniper.state.status == "IDLE"
    assert sniper.state.allocated_usd == 5.25
    assert sniper.use_rocket is True
    assert sniper.to_dict()["status"] == "IDLE"


def test_flash_sniper_places_dip_trap_when_idle():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25, dip_depth_pct=0.0200)
    client_mock = MagicMock()
    client_mock.create_limit_order.return_value = {"retCode": 0, "result": {"orderId": "sniper_ord_1"}}

    cur_price = 4.500
    avail_usdt = 10.00
    res = sniper.tick(
        client=client_mock,
        cur_price=cur_price,
        avail_usdt=avail_usdt,
        free_qty=0.0,
        lead_lag_status="CLEAR",
        price_decimals=3,
        qty_decimals=2,
    )

    assert res is not None
    assert res["action"] == "BUY_PLACED"
    expected_price = round(4.500 * (1 - 0.0200), 3)  # 4.410
    assert res["price"] == expected_price
    assert sniper.state.status == "HUNTING"
    assert sniper.state.buy_order_id == "sniper_ord_1"
    assert sniper.state.buy_price == expected_price
    client_mock.create_limit_order.assert_called_once()


def test_flash_sniper_lead_lag_crash_aborts_trap():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25)
    sniper.state.status = "HUNTING"
    sniper.state.buy_order_id = "sniper_ord_1"
    sniper.state.buy_price = 0.9750

    client_mock = MagicMock()
    client_mock.cancel_order.return_value = {"retCode": 0}

    res = sniper.tick(
        client=client_mock,
        cur_price=4.500,
        avail_usdt=10.00,
        free_qty=0.0,
        lead_lag_status="CRASH",
        price_decimals=3,
        qty_decimals=2,
    )

    assert res is None
    assert sniper.state.status == "IDLE"
    assert sniper.state.buy_order_id is None
    client_mock.cancel_order.assert_called_once_with("NEARUSDT", "sniper_ord_1")


def test_flash_sniper_places_maker_tp_when_rocket_disabled():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25, tp_pct=0.0150, use_rocket=False)
    sniper.state.status = "POSITION_HELD"
    sniper.state.entry_price = 4.410
    sniper.state.position_qty = 1.19

    client_mock = MagicMock()
    client_mock.create_limit_order.return_value = {"retCode": 0, "result": {"orderId": "sniper_tp_1"}}

    res = sniper.tick(
        client=client_mock,
        cur_price=4.450,
        avail_usdt=5.00,
        free_qty=1.19,
        lead_lag_status="CLEAR",
        price_decimals=3,
        qty_decimals=2,
    )

    assert res is not None
    assert res["action"] == "TP_PLACED"
    expected_tp = round(4.410 * (1 + 0.0150), 3)  # 4.476
    assert res["tp_price"] == expected_tp
    assert sniper.state.status == "TP_PLACED"
    assert sniper.state.tp_order_id == "sniper_tp_1"
    client_mock.create_limit_order.assert_called_once()


def test_flash_sniper_rocket_activation_and_trailing():
    sniper = FlashSniperController(
        symbol="NEARUSDT",
        budget_usd=5.25,
        use_rocket=True,
        rocket_activation_pct=0.0150,
        rocket_callback_pct=0.0035,
        rocket_floor_pct=0.0120,
    )
    sniper.state.status = "POSITION_HELD"
    sniper.state.entry_price = 4.000
    sniper.state.position_qty = 1.31

    client_mock = MagicMock()

    # 1. Price rebounds +1.0% (not yet activated)
    res1 = sniper.tick(client_mock, cur_price=4.040, avail_usdt=5.0, free_qty=1.31, lead_lag_status="CLEAR", price_decimals=3, qty_decimals=2)
    assert res1 is None
    assert sniper.state.status == "POSITION_HELD"

    # 2. Price rebounds +1.50% -> Rocket activates!
    res2 = sniper.tick(client_mock, cur_price=4.060, avail_usdt=5.0, free_qty=1.31, lead_lag_status="CLEAR", price_decimals=3, qty_decimals=2)
    assert res2 is not None
    assert res2["event"] == "ROCKET_ACTIVATED"
    assert sniper.state.status == "ROCKET_ACTIVE"
    assert sniper.state.peak_price == 4.060
    expected_floor = round(4.000 * 1.0120, 3)  # 4.048
    assert sniper.state.floor_price == expected_floor

    # 3. Price rockets up to 4.200 (+5.0%) -> Peak ratchets up!
    res3 = sniper.tick(client_mock, cur_price=4.200, avail_usdt=5.0, free_qty=1.31, lead_lag_status="CLEAR", price_decimals=3, qty_decimals=2)
    assert sniper.state.peak_price == 4.200
    expected_stop = round(4.200 * (1 - 0.0035), 3)  # 4.185
    assert sniper.state.stop_price == expected_stop


def test_flash_sniper_rocket_exit_on_pullback():
    sniper = FlashSniperController(
        symbol="NEARUSDT",
        budget_usd=5.25,
        use_rocket=True,
        rocket_activation_pct=0.0150,
        rocket_callback_pct=0.0035,
        rocket_floor_pct=0.0120,
    )
    sniper.state.status = "ROCKET_ACTIVE"
    sniper.state.entry_price = 4.000
    sniper.state.position_qty = 1.31
    sniper.state.peak_price = 4.200
    sniper.state.stop_price = 4.185
    sniper.state.floor_price = 4.048

    client_mock = MagicMock()
    client_mock.create_market_order.return_value = {"retCode": 0}

    # Price pulls back to 4.180 (below stop 4.185) -> triggers market exit!
    res = sniper.tick(client_mock, cur_price=4.180, avail_usdt=5.0, free_qty=1.31, lead_lag_status="CLEAR", price_decimals=3, qty_decimals=2)
    assert res is not None
    assert res["action"] == "ROCKET_EXIT"
    assert sniper.state.status == "IDLE"
    assert sniper.state.completed_cycles == 1
    assert sniper.state.total_profit_usd > 0.0
    client_mock.create_market_order.assert_called_once_with("NEARUSDT", "Sell", 1.31)


def test_flash_sniper_sync_cycle_completion():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25)
    sniper.state.status = "TP_PLACED"
    sniper.state.position_qty = 1.19
    sniper.state.entry_price = 4.410
    sniper.state.tp_price = 4.476
    sniper.state.tp_order_id = "sniper_tp_1"

    # Open orders no longer contain sniper TP order (it filled!)
    sniper.sync_on_exchange_orders([])

    assert sniper.state.status == "IDLE"
    assert sniper.state.completed_cycles == 1
    assert sniper.state.total_profit_usd > 0.0
    assert sniper.state.position_qty == 0.0
