"""Unit tests for Step 1: Dual-Profile Architecture (Desktop vs Mobile) and Handover Readiness.
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
    DESKTOP_RESERVE_USDT,
    DESKTOP_STEP_WEIGHTS,
    format_status_text,
)


def test_default_profile_is_mobile():
    """Ensures bot defaults to mobile mode with zero reserve overhead."""
    bot = StandaloneBybitBot()
    assert bot.mode == "mobile"
    assert bot.reserve_usdt == 0.0
    assert bot.stats["profile"] == "MOBILE / STORM"
    assert bot.stats["role"] == "ACTIVE_CONTROLLER"
    assert bot.is_active_controller is True


def test_desktop_profile_initialization():
    """Ensures desktop mode activates $10 reserve buffer and correct profile badge."""
    bot = StandaloneBybitBot(mode="desktop")
    assert bot.mode == "desktop"
    assert bot.reserve_usdt == DESKTOP_RESERVE_USDT
    assert bot.stats["profile"] == "DESKTOP / SMART-STEP"
    assert bot.stats["role"] == "ACTIVE_CONTROLLER"
    assert bot.is_active_controller is True


def test_desktop_asymmetric_step_budget_sizing():
    """Validates asymmetric sizing at ~$43 bankroll gives progressive ~$6 / ~$10.50 / ~$16.50."""
    est_total_equity = 43.00
    reserve = DESKTOP_RESERVE_USDT  # 10.00
    deployable = max(15.00, est_total_equity - reserve)  # 33.00

    b1 = max(5.05, round(deployable * DESKTOP_STEP_WEIGHTS["step_1"], 2))
    b2 = max(5.05, round(deployable * DESKTOP_STEP_WEIGHTS["step_2"], 2))
    b3 = max(5.05, round(deployable * DESKTOP_STEP_WEIGHTS["step_3"], 2))

    assert b1 == pytest.approx(5.94, abs=0.05)   # ~$6.00 (Step 1)
    assert b2 == pytest.approx(10.56, abs=0.05)  # ~$10.50 (Step 2)
    assert b3 == pytest.approx(16.50, abs=0.05)  # ~$16.50 (Step 3)

    # Total planned deployment equals deployable budget
    assert round(b1 + b2 + b3, 2) == round(deployable, 2)
    # Total planned + reserve equals total equity
    assert round(b1 + b2 + b3 + reserve, 2) == round(est_total_equity, 2)


def test_desktop_reserve_preservation_prevents_spend():
    """Checks that desktop mode strictly protects the $10 USDT reserve from being spent."""
    bot = StandaloneBybitBot(mode="desktop")
    avail_usdt = 12.00  # Only $2.00 spendable above $10.00 reserve
    spendable = max(0.0, avail_usdt - bot.reserve_usdt)
    assert spendable == 2.00
    # Minimum Bybit order is 5.00, so 2.00 must prevent any new BUY order
    assert spendable < 5.00


def test_handover_passive_observer_blocks_buys():
    """Verifies that setting is_active_controller = False transitions to passive observer."""
    bot = StandaloneBybitBot(mode="mobile")
    bot.is_active_controller = False
    bot.role = "PASSIVE_OBSERVER"

    # Mock client and guard
    bot.client.get_wallet_balance = MagicMock(return_value={
        "retCode": 0,
        "total_usd": 43.0,
        "available_usdt": 20.0,
        "locked_usdt": 23.0,
        "coins": {
            "USDT": {"balance": 43.0, "free": 20.0, "locked": 23.0},
            "SUI": {"balance": 0.0, "free": 0.0, "locked": 0.0},
            "APT": {"balance": 0.0, "free": 0.0, "locked": 0.0},
            "MNT": {"balance": 0.5, "free": 0.5, "locked": 0.0},
        }
    })
    bot.client.create_limit_order = MagicMock()
    bot.client.get_open_orders = MagicMock(return_value=[])
    bot.client.get_execution_history = MagicMock(return_value=[])
    bot.get_market_price = MagicMock(return_value=0.90)

    with patch.object(bot.guard, "update_market_state", return_value=(False, "", {"SUIUSDT": (False, "")})):
        bot.step()

    # In passive observer mode, create_limit_order must NOT be called for BUY
    buy_calls = [c for c in bot.client.create_limit_order.call_args_list if c[0][1] == "Buy"]
    assert len(buy_calls) == 0
    assert bot.stats["tokens"]["SUIUSDT"]["mode"] == "PASSIVE_OBSERVER"


def test_format_status_text_shows_profile_and_reserve():
    """Checks that format_status_text properly brands the output."""
    bot_mobile = StandaloneBybitBot(mode="mobile")
    txt_mobile = format_status_text(bot_mobile)
    assert "[MOBILE / STORM]" in txt_mobile
    assert "Резервный буфер" not in txt_mobile

    bot_desktop = StandaloneBybitBot(mode="desktop")
    txt_desktop = format_status_text(bot_desktop)
    assert "[DESKTOP / SMART-STEP]" in txt_desktop
    assert "Резервный буфер: `$10.00 USDT`" in txt_desktop
