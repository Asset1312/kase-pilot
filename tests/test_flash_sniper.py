"""Unit tests for the Flash Sniper (Crash Harvester / Wick Catcher) module."""
import pytest
from unittest.mock import MagicMock
from bybit_standalone_bot import (
    FlashSniperController,
    FlashSniperState,
    SNIPER_ORDER_LINK_PREFIX,
    SNIPER_BUDGET_USD,
    SNIPER_DIP_DEPTH_PCT,
    SNIPER_TP_PCT,
)


def test_flash_sniper_init():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25)
    assert sniper.symbol == "NEARUSDT"
    assert sniper.budget_usd == 5.25
    assert sniper.state.status == "IDLE"
    assert sniper.state.allocated_usd == 5.25
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


def test_flash_sniper_places_instant_maker_tp_when_position_held():
    sniper = FlashSniperController(symbol="NEARUSDT", budget_usd=5.25, tp_pct=0.0150)
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
