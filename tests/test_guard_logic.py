"""
Unit tests for MarketGuard, Adaptive Spacing, Inventory-Aware Sizing, and Fee-Proof Breakeven.
"""

import time
import pytest


class MockMarketGuard:
    def __init__(self):
        self.cooldown_active = False
        self.cooldown_start_time = 0.0
        self.cooldown_reason = ""
        self.volatility_regime = "NORMAL"
        self.step1_discount = 0.0055
        self.step2_discount = 0.0175

    def evaluate_dump_triggers(self, btc_1m_chg, btc_3m_chg, sui_1m_chg, sui_3m_chg):
        """Dual dump check: BTC Lead-Lag (-0.35% / -0.70%) OR SUI Idiosyncratic (-0.60% / -1.20%)."""
        if btc_1m_chg <= -0.0035:
            return True, f"BTC 1m Flash Dump ({btc_1m_chg*100:.2f}%)"
        if btc_3m_chg <= -0.0070:
            return True, f"BTC 3m Cumulative Dump ({btc_3m_chg*100:.2f}%)"
        if sui_1m_chg <= -0.0060:
            return True, f"SUI 1m Idiosyncratic Dump ({sui_1m_chg*100:.2f}%)"
        if sui_3m_chg <= -0.0120:
            return True, f"SUI 3m Cumulative Dump ({sui_3m_chg*100:.2f}%)"
        return False, ""

    def evaluate_stabilization(self, elapsed_sec, btc_low0, btc_low1, sui_low0, sui_low1, sui_1m_chg):
        """Smart exit: >= 600s AND neither BTC nor SUI made a lower low AND SUI candle not dumping."""
        if elapsed_sec < 600:
            return False, "Cooldown timer active (< 10 min)"
        if btc_low0 < btc_low1:
            return False, "BTC still making lower lows"
        if sui_low0 < sui_low1:
            return False, "SUI still making lower lows"
        if sui_1m_chg < -0.0010:
            return False, "SUI current candle red"
        return True, "Stabilized"

    def evaluate_volatility(self, high_15m, low_15m):
        """Dynamic step spacing: Normal (-0.55% / -1.75%) vs Storm (-1.20% / -2.80%)."""
        range_pct = (high_15m - low_15m) / low_15m
        if range_pct > 0.0120:
            self.volatility_regime = "STORM"
            self.step1_discount = 0.0120
            self.step2_discount = 0.0280
        else:
            self.volatility_regime = "NORMAL"
            self.step1_discount = 0.0055
            self.step2_discount = 0.0175
        return self.volatility_regime


def test_btc_flash_dump_trigger():
    guard = MockMarketGuard()
    # BTC dumps -0.40% in 1 min, SUI is quiet
    fired, reason = guard.evaluate_dump_triggers(-0.0040, -0.0050, -0.0010, -0.0020)
    assert fired is True
    assert "BTC 1m Flash Dump" in reason


def test_sui_idiosyncratic_dump_trigger():
    guard = MockMarketGuard()
    # BTC flat (+0.02%), but SUI dumps -0.75%
    fired, reason = guard.evaluate_dump_triggers(0.0002, 0.0005, -0.0075, -0.0090)
    assert fired is True
    assert "SUI 1m Idiosyncratic Dump" in reason


def test_normal_market_no_dump():
    guard = MockMarketGuard()
    fired, reason = guard.evaluate_dump_triggers(-0.0010, -0.0020, -0.0020, -0.0040)
    assert fired is False
    assert reason == ""


def test_smart_stabilization_exit():
    guard = MockMarketGuard()
    # 1. Less than 10 min -> cannot exit
    ok, msg = guard.evaluate_stabilization(300, 76000, 75900, 0.710, 0.705, 0.001)
    assert ok is False
    assert "Cooldown timer active" in msg

    # 2. 12 min passed, but SUI still making lower low (0.695 < 0.700) -> cannot exit!
    ok, msg = guard.evaluate_stabilization(720, 76000, 75900, 0.695, 0.700, -0.0005)
    assert ok is False
    assert "SUI still making lower lows" in msg

    # 3. 12 min passed, both BTC and SUI formed higher/equal lows, green candle -> CAN EXIT!
    ok, msg = guard.evaluate_stabilization(720, 76100, 76000, 0.702, 0.700, 0.002)
    assert ok is True
    assert "Stabilized" in msg


def test_dynamic_volatility():
    guard = MockMarketGuard()
    # Low vol (range 0.5%)
    regime = guard.evaluate_volatility(0.720, 0.7164)
    assert regime == "NORMAL"
    assert guard.step1_discount == 0.0055
    assert guard.step2_discount == 0.0175

    # High vol (range 2.5%)
    regime = guard.evaluate_volatility(0.730, 0.712)
    assert regime == "STORM"
    assert guard.step1_discount == 0.0120
    assert guard.step2_discount == 0.0280


def test_fee_proof_soft_breakeven():
    entry_price = 0.7000
    qty = 7.15
    cost_usd = entry_price * qty  # $5.005
    buy_fee = cost_usd * 0.0010   # 0.10%

    # Soft Breakeven TP at +0.38%
    sell_price = round(entry_price * 1.0038, 4)  # 0.7027
    gross_revenue = sell_price * qty              # $5.0243
    sell_fee = gross_revenue * 0.0010            # 0.10%

    net_profit = gross_revenue - cost_usd - buy_fee - sell_fee
    # Net profit must be strictly POSITIVE!
    assert net_profit > 0.005, f"Net profit was {net_profit}, expected positive"
    net_profit_pct = (net_profit / cost_usd) * 100
    assert net_profit_pct >= 0.15, f"Net profit pct was {net_profit_pct:.3f}%, expected >= +0.15%"


def test_inventory_aware_sizing():
    # Min order on Bybit is 5.00 USDT
    # Case 1: Total cash = 11.16, no position (sui_val = 0)
    avail = 11.16
    alloc_1 = max(5.05, round(avail * 0.45, 2))
    alloc_2 = max(5.05, round(avail * 0.45, 2))
    buffer = round(avail - alloc_1 - alloc_2, 2)
    assert alloc_1 >= 5.00
    assert alloc_2 >= 5.00
    assert alloc_1 + alloc_2 <= avail
    assert buffer >= 1.00

    # Case 2: Step 1 already bought (sui_val = 5.10), avail_cash = 6.06
    pos_val = 5.10
    avail_remaining = 6.06
    # In this case, Step 1 is BLOCKED. All remaining cash is reserved for Step 2
    step1_allowed = pos_val < 5.00
    assert step1_allowed is False
    alloc_step2 = min(avail_remaining, max(5.05, round(avail_remaining * 0.90, 2)))
    assert alloc_step2 >= 5.00
    assert alloc_step2 <= avail_remaining
