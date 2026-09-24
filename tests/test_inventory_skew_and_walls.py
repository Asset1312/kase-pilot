"""Unit tests for InventorySkewController and L2WallScanner (Gen 3 Grid Components)."""
import pytest
from unittest.mock import MagicMock
from bybit_standalone_bot import (
    InventorySkewController,
    L2WallScanner,
)


def test_inventory_skew_multipliers():
    controller = InventorySkewController(base_tp_pct=0.0070)

    # Step 1: no skew (1.0x)
    assert controller.get_skewed_step_offset(1, 0.0100) == 0.0100

    # Step 2: 1.25x deeper
    assert controller.get_skewed_step_offset(2, 0.0200) == 0.0250

    # Step 3: 1.50x deeper
    assert controller.get_skewed_step_offset(3, 0.0400) == 0.0600


def test_inventory_skew_take_profit():
    controller = InventorySkewController(base_tp_pct=0.0070)

    # 1 step held -> standard TP (+0.70%)
    assert controller.get_skewed_tp_pct(1) == 0.0070

    # 2 steps held -> moderate TP (+0.45%)
    assert controller.get_skewed_tp_pct(2) == 0.0045

    # 3 steps held -> aggressive fast de-risking (+0.25%)
    assert controller.get_skewed_tp_pct(3) == 0.0025
    assert controller.get_skewed_tp_pct(4) == 0.0025


def test_l2_wall_scanner_front_runs_large_bid_wall():
    client_mock = MagicMock()
    # Mock orderbook with a 45,000 SUI wall at $0.9450
    client_mock._request.return_value = {
        "retCode": 0,
        "result": {
            "b": [
                ["0.9480", "1200.0"],
                ["0.9470", "2500.0"],
                ["0.9450", "45000.0"],  # Institutional wall > 30,000
                ["0.9430", "3000.0"],
            ],
            "a": [["0.9490", "5000.0"]]
        }
    }

    scanner = L2WallScanner(client=client_mock, min_wall_qty=30000.0)

    # Base calculated price is $0.9452 (window +-0.35% is [0.9419, 0.9485])
    # The wall is at $0.9450. Scanner should front-run it by 1 tick (+0.0001) -> $0.9451
    front_price = scanner.find_front_run_price("SUIUSDT", calc_price=0.9452, window_pct=0.0035, tick_size=0.0001, price_decimals=4)

    assert front_price == 0.9451
    client_mock._request.assert_called_once()


def test_l2_wall_scanner_ignores_small_clusters():
    client_mock = MagicMock()
    # Mock orderbook where no level reaches min_wall_qty (all < 30000 and < $15k USD)
    client_mock._request.return_value = {
        "retCode": 0,
        "result": {
            "b": [
                ["0.9480", "1200.0"],
                ["0.9470", "2500.0"],
                ["0.9450", "8000.0"],
            ],
            "a": []
        }
    }

    scanner = L2WallScanner(client=client_mock, min_wall_qty=30000.0, min_wall_usd=15000.0)

    # With no qualifying wall, it should return the original calculated price unchanged
    calc_p = 0.9455
    res = scanner.find_front_run_price("SUIUSDT", calc_price=calc_p)
    assert res == calc_p


def test_l2_wall_scanner_exception_fallback():
    client_mock = MagicMock()
    client_mock._request.side_effect = Exception("Connection timeout")

    scanner = L2WallScanner(client=client_mock)
    calc_p = 0.9450
    # On exception, gracefully falls back to calc_price without crashing
    res = scanner.find_front_run_price("SUIUSDT", calc_price=calc_p)
    assert res == calc_p
