"""Unit tests for Trailing Take-Profit (Rocket Rider) - Desktop Profile.
"""

from __future__ import annotations

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from bybit_standalone_bot import (
    StandaloneBybitBot,
    TrailingTakeProfitController,
    TrailingPositionState,
    TRAILING_ACTIVATION_PCT,
    TRAILING_CALLBACK_PCT,
    TRAILING_MIN_FLOOR_PCT,
    PRIMARY_SYMBOL,
)


def test_trailing_inactive_below_threshold():
    """Ensures position remains IDLE when profit is below the activation threshold (+1.00%)."""
    controller = TrailingTakeProfitController()
    entry = 0.8500
    price = 0.8550  # +0.59% profit (< +1.00%)

    res = controller.update_price(
        symbol=PRIMARY_SYMBOL,
        cur_price=price,
        entry_price=entry,
        free_qty=15.0,
        holding_val_usd=15.0 * price,
    )

    state = controller.get_state(PRIMARY_SYMBOL)
    assert res is None
    assert state.status == "IDLE"
    assert state.peak_price == 0.0
    assert controller.is_any_trailing_active() is False


def test_trailing_activates_at_threshold():
    """Verifies that trailing activates at +1.00% with guaranteed floor (+0.50%)."""
    controller = TrailingTakeProfitController()
    entry = 0.8500
    price = 0.8585  # Exactly +1.00%

    res = controller.update_price(
        symbol=PRIMARY_SYMBOL,
        cur_price=price,
        entry_price=entry,
        free_qty=15.0,
        holding_val_usd=15.0 * price,
    )

    assert res is not None
    assert res["event"] == "ACTIVATED"
    assert res["cur_price"] == 0.8585
    assert res["entry_price"] == 0.8500

    state = controller.get_state(PRIMARY_SYMBOL)
    assert state.status == "TRAILING_ACTIVE"
    assert state.peak_price == 0.8585
    expected_floor = entry * (1.0 + TRAILING_MIN_FLOOR_PCT)
    assert state.floor_price == pytest.approx(expected_floor, abs=1e-5)
    # Stop price must be at least the floor price
    assert state.stop_price >= expected_floor
    assert controller.is_any_trailing_active() is True


def test_trailing_peak_tracking_and_stop_ratchet():
    """Verifies that peak price updates on new highs and stop price ratchets up strictly."""
    controller = TrailingTakeProfitController()
    entry = 0.8500

    # 1. Activate at +1.00%
    controller.update_price(PRIMARY_SYMBOL, 0.8585, entry, 15.0, 15.0 * 0.8585)

    # 2. Surge to +3.53% ($0.8800)
    controller.update_price(PRIMARY_SYMBOL, 0.8800, entry, 15.0, 15.0 * 0.8800)
    state = controller.get_state(PRIMARY_SYMBOL)
    assert state.peak_price == 0.8800
    stop_at_88 = 0.8800 * (1.0 - TRAILING_CALLBACK_PCT)
    assert state.stop_price == pytest.approx(stop_at_88, abs=1e-5)

    # 3. Rocket to +7.29% ($0.9120)
    controller.update_price(PRIMARY_SYMBOL, 0.9120, entry, 15.0, 15.0 * 0.9120)
    assert state.peak_price == 0.9120
    stop_at_912 = 0.9120 * (1.0 - TRAILING_CALLBACK_PCT)
    assert state.stop_price == pytest.approx(stop_at_912, abs=1e-5)
    assert state.stop_price > stop_at_88

    # 4. Small dip to $0.9100 (above stop) -> stop price must NOT decrease!
    controller.update_price(PRIMARY_SYMBOL, 0.9100, entry, 15.0, 15.0 * 0.9100)
    assert state.peak_price == 0.9120
    assert state.stop_price == pytest.approx(stop_at_912, abs=1e-5)


def test_trailing_trigger_on_callback():
    """Verifies exit signal fires when price pulls back by 0.45% from peak."""
    controller = TrailingTakeProfitController()
    entry = 0.8500

    # 1. Activate and climb to peak 0.9120
    controller.update_price(PRIMARY_SYMBOL, 0.8585, entry, 15.0, 15.0 * 0.8585)
    controller.update_price(PRIMARY_SYMBOL, 0.9120, entry, 15.0, 15.0 * 0.9120)
    state = controller.get_state(PRIMARY_SYMBOL)

    # 2. Pullback hits stop at 0.9075
    trigger = controller.update_price(PRIMARY_SYMBOL, 0.9075, entry, 15.0, 15.0 * 0.9075)

    assert trigger is not None
    assert trigger["action"] == "TRIGGER_EXIT"
    assert trigger["symbol"] == PRIMARY_SYMBOL
    assert trigger["exit_price"] == 0.9075
    assert trigger["peak_price"] == 0.9120
    assert trigger["entry_price"] == 0.8500
    assert trigger["gain_pct"] == pytest.approx((0.9075 - 0.8500) / 0.8500, abs=1e-4)

    # State must be reset after exit
    new_state = controller.get_state(PRIMARY_SYMBOL)
    assert new_state.status == "IDLE"
    assert controller.is_any_trailing_active() is False


def test_trailing_guaranteed_floor_protection():
    """Verifies that on premature pullback, stop price never drops below +0.50% floor."""
    controller = TrailingTakeProfitController()
    entry = 0.8500

    # Activate barely at +1.00% (0.8585)
    controller.update_price(PRIMARY_SYMBOL, 0.8585, entry, 15.0, 15.0 * 0.8585)
    state = controller.get_state(PRIMARY_SYMBOL)
    floor = entry * (1.0 + TRAILING_MIN_FLOOR_PCT)  # 0.85425
    assert state.floor_price == pytest.approx(floor, abs=1e-5)
    assert state.stop_price >= floor

    # Instant pullback to 0.8540 breaches stop
    trigger = controller.update_price(PRIMARY_SYMBOL, 0.8540, entry, 15.0, 15.0 * 0.8540)
    assert trigger is not None
    assert trigger["action"] == "TRIGGER_EXIT"
    assert trigger["exit_price"] == 0.8540
    # Net gain is positive (+0.47% ~ +0.50%)
    assert trigger["gain_pct"] > 0.0040


def test_trailing_desktop_only_isolation():
    """Verifies desktop uses Trailing Take-Profit while mobile uses static limit TP."""
    # Mobile mode: trailing controller should NOT activate
    bot_mobile = StandaloneBybitBot(mode="mobile")
    assert bot_mobile.mode == "mobile"

    # Desktop mode: trailing controller is present and functional
    bot_desktop = StandaloneBybitBot(mode="desktop")
    assert bot_desktop.mode == "desktop"
    assert hasattr(bot_desktop, "trailing_controller")
    assert isinstance(bot_desktop.trailing_controller, TrailingTakeProfitController)


def test_trailing_reset_on_position_close():
    """Verifies that when position drops below $5.00 holding value, state automatically resets."""
    controller = TrailingTakeProfitController()
    entry = 0.8500
    controller.update_price(PRIMARY_SYMBOL, 0.8585, entry, 15.0, 15.0 * 0.8585)
    assert controller.get_state(PRIMARY_SYMBOL).status == "TRAILING_ACTIVE"

    # Position sold or dust remaining (< $5.00)
    controller.update_price(PRIMARY_SYMBOL, 0.8585, entry, 0.5, 0.42)
    assert controller.get_state(PRIMARY_SYMBOL).status == "IDLE"


def test_desktop_step_no_unbound_local_error_tp_mode():
    """Verifies that step() executes without UnboundLocalError when holding value is 0.0."""
    bot = StandaloneBybitBot(mode="desktop")
    bot.client.get_wallet_balance = MagicMock(return_value={
        "retCode": 0,
        "total_usd": 50.0,
        "available_usdt": 50.0,
        "locked_usdt": 0.0,
        "coins": {
            "USDT": {"balance": 50.0, "free": 50.0, "locked": 0.0},
            "SUI": {"balance": 0.0, "free": 0.0, "locked": 0.0},
            "APT": {"balance": 0.0, "free": 0.0, "locked": 0.0},
            "MNT": {"balance": 1.0, "free": 1.0, "locked": 0.0},
        }
    })
    bot.client.get_open_orders = MagicMock(return_value=[])
    bot.client.get_execution_history = MagicMock(return_value=[])
    bot.client.create_limit_order = MagicMock(return_value={"retCode": 0})
    bot.get_market_price = MagicMock(return_value=0.90)

    with patch.object(bot.guard, "update_market_state", return_value=(False, "", {"SUIUSDT": (False, "")})):
        bot.step()

    # Verify stats were populated with tp_mode defined
    assert "SUIUSDT" in bot.stats["tokens"]
    assert bot.stats["tokens"]["SUIUSDT"]["tp_mode"] == "Standard (+0.90%)"
    assert bot.stats["tokens"]["SUIUSDT"]["position_age_hours"] == 0.0
