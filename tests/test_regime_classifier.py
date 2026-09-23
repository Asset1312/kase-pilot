"""
Unit tests for Market Regime Classifier, REGIME_PROFILES, Hysteresis, and Cycle Lock.
"""
import pytest
import time
from bybit_standalone_bot import MarketGuard, REGIME_PROFILES, StandaloneBybitBot


def test_regime_profiles_structure():
    assert "CALM" in REGIME_PROFILES
    assert "NORMAL" in REGIME_PROFILES
    assert "STORM" in REGIME_PROFILES

    calm = REGIME_PROFILES["CALM"]
    assert calm["is_calm_split"] is True
    assert calm["budget_1a"] >= 5.00
    assert calm["budget_1b"] >= 5.00
    assert calm["step_1a_discount"] == 0.0035
    assert calm["step_1b_discount"] == 0.0065
    assert calm["step_3_discount"] == 0.0350

    norm = REGIME_PROFILES["NORMAL"]
    assert norm["is_calm_split"] is False
    assert norm["step_1_discount"] == 0.0055

    storm = REGIME_PROFILES["STORM"]
    assert storm["is_calm_split"] is False
    assert storm["step_1_discount"] == 0.0110


def test_classify_market_regime_calm():
    guard = MarketGuard()
    # 8 candles with tight 0.40% range: close = 1.000, high = 1.002, low = 0.998
    klines_15m = [
        ["1700000000000", "1.000", "1.002", "0.998", "1.000", "1000"]
        for _ in range(8)
    ]
    regime, amp = guard.classify_market_regime("SUIUSDT", klines_15m)
    assert regime == "CALM"
    assert amp < 0.80


def test_classify_market_regime_storm():
    guard = MarketGuard()
    # 8 candles with wide 2.50% range: close = 1.000, high = 1.020, low = 0.995
    klines_15m = [
        ["1700000000000", "1.000", "1.020", "0.995", "1.000", "1000"]
        for _ in range(8)
    ]
    regime, amp = guard.classify_market_regime("SUIUSDT", klines_15m)
    assert regime == "STORM"
    assert amp >= 1.50


def test_classify_market_regime_fail_safe_on_btc_crash():
    guard = MarketGuard()
    guard.lead_lag_status = "CRASH"
    klines_15m = [
        ["1700000000000", "1.000", "1.001", "0.999", "1.000", "1000"]
        for _ in range(8)
    ]
    # Even though local range is super calm (<0.3%), BTC CRASH forces STORM
    regime, _ = guard.classify_market_regime("SUIUSDT", klines_15m)
    assert regime == "STORM"


def test_classify_market_regime_hysteresis():
    guard = MarketGuard()
    # 1. Start with CALM
    calm_klines = [
        ["1700000000000", "1.000", "1.002", "0.998", "1.000", "1000"]
        for _ in range(8)
    ]
    regime1, _ = guard.classify_market_regime("SUIUSDT", calm_klines)
    assert regime1 == "CALM"

    # 2. Next tick: mild range bump to NORMAL (0.90% range), but hysteresis (30 min) keeps CALM
    mild_klines = [
        ["1700000000000", "1.000", "1.005", "0.996", "1.000", "1000"]
        for _ in range(8)
    ]
    regime2, _ = guard.classify_market_regime("SUIUSDT", mild_klines)
    assert regime2 == "CALM"

    # 3. But a jump to STORM bypasses hysteresis for safety!
    storm_klines = [
        ["1700000000000", "1.000", "1.020", "0.995", "1.000", "1000"]
        for _ in range(8)
    ]
    regime3, _ = guard.classify_market_regime("SUIUSDT", storm_klines)
    assert regime3 == "STORM"


def test_cycle_lock_state():
    bot = StandaloneBybitBot(mode="desktop", enable_telegram=False)
    assert "SUIUSDT" in bot.token_locked_regime
    assert bot.token_locked_regime["SUIUSDT"] is None

    # Simulating holding position lock
    bot.token_locked_regime["SUIUSDT"] = "CALM"
    assert bot.token_locked_regime["SUIUSDT"] == "CALM"
