import pytest
from unittest.mock import MagicMock, patch
from bybit_standalone_bot import (
    StandaloneBybitBot,
    PRIMARY_SYMBOL,
    SECONDARY_SYMBOL,
    TERTIARY_SYMBOL,
    DUAL_PAIR_ACTIVATION_EQUITY,
    DUAL_PAIR_DEACTIVATION_EQUITY,
    TRIO_PAIR_ACTIVATION_EQUITY,
    TRIO_PAIR_DEACTIVATION_EQUITY,
    TOKEN_METADATA,
    format_status_text,
    format_trades_text,
)


@pytest.fixture
def mock_bot():
    with patch("bybit_standalone_bot.BybitV5Client"):
        bot = StandaloneBybitBot(mode="desktop", enable_telegram=False, is_24x7=True)
        bot.client = MagicMock()
        return bot


def test_token_metadata_has_three_coins():
    assert PRIMARY_SYMBOL in TOKEN_METADATA
    assert SECONDARY_SYMBOL in TOKEN_METADATA
    assert TERTIARY_SYMBOL in TOKEN_METADATA
    assert TOKEN_METADATA[PRIMARY_SYMBOL]["base_coin"] == "SUI"
    assert TOKEN_METADATA[SECONDARY_SYMBOL]["base_coin"] == "NEAR"
    assert TOKEN_METADATA[TERTIARY_SYMBOL]["base_coin"] == "AVAX"


def test_capital_allocation_single_mode_below_70(mock_bot):
    # Deposit $53.85: Should be Single SUI 100%
    mock_bot.client.get_wallet_balance.return_value = {
        "retCode": 0,
        "available_usdt": 21.81,
        "locked_usdt": 0.0,
        "total_usd": 21.81,
        "coins": {
            "SUI": {"free": 31.67, "locked": 0.0},
            "NEAR": {"free": 0.0, "locked": 0.0},
            "AVAX": {"free": 0.0, "locked": 0.0},
        },
    }
    mock_bot.client.get_tickers.side_effect = lambda sym: [{"lastPrice": "1.0100"}]
    mock_bot.client.get_open_orders.return_value = []
    mock_bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))

    mock_bot.step()

    assert mock_bot.dual_mode_active is False
    assert mock_bot.trio_mode_active is False
    assert "Single" in mock_bot.stats["portfolio_mode"]
    assert PRIMARY_SYMBOL in mock_bot.stats["tokens"]
    assert SECONDARY_SYMBOL not in mock_bot.stats["tokens"]
    assert TERTIARY_SYMBOL not in mock_bot.stats["tokens"]


def test_capital_allocation_dual_mode_at_70(mock_bot):
    # Deposit $75: Should activate Dual (50% SUI / 50% NEAR)
    mock_bot.client.get_wallet_balance.return_value = {
        "retCode": 0,
        "available_usdt": 75.0,
        "locked_usdt": 0.0,
        "total_usd": 75.0,
        "coins": {},
    }
    mock_bot.client.get_tickers.side_effect = lambda sym: [{"lastPrice": "1.0000"}]
    mock_bot.client.get_open_orders.return_value = []
    mock_bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))

    mock_bot.step()

    assert mock_bot.dual_mode_active is True
    assert mock_bot.trio_mode_active is False
    assert "Dual" in mock_bot.stats["portfolio_mode"]
    assert PRIMARY_SYMBOL in mock_bot.stats["tokens"]
    assert SECONDARY_SYMBOL in mock_bot.stats["tokens"]
    assert TERTIARY_SYMBOL not in mock_bot.stats["tokens"]


def test_capital_allocation_trio_mode_at_115(mock_bot):
    # Deposit $120: Should activate Trio (33% SUI / 33% NEAR / 33% AVAX)
    mock_bot.client.get_wallet_balance.return_value = {
        "retCode": 0,
        "available_usdt": 120.0,
        "locked_usdt": 0.0,
        "total_usd": 120.0,
        "coins": {},
    }
    mock_bot.client.get_tickers.side_effect = lambda sym: [{"lastPrice": "1.0000"}]
    mock_bot.client.get_open_orders.return_value = []
    mock_bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))

    mock_bot.step()

    assert mock_bot.trio_mode_active is True
    assert mock_bot.dual_mode_active is True
    assert "Trio" in mock_bot.stats["portfolio_mode"]
    assert PRIMARY_SYMBOL in mock_bot.stats["tokens"]
    assert SECONDARY_SYMBOL in mock_bot.stats["tokens"]
    assert TERTIARY_SYMBOL in mock_bot.stats["tokens"]


def test_capital_allocation_hysteresis_deactivation(mock_bot):
    # Was in trio mode, equity drops to $100 -> Drops back to dual mode (< $105)
    mock_bot.trio_mode_active = True
    mock_bot.dual_mode_active = True

    mock_bot.client.get_wallet_balance.return_value = {
        "retCode": 0,
        "available_usdt": 100.0,
        "locked_usdt": 0.0,
        "total_usd": 100.0,
        "coins": {},
    }
    mock_bot.client.get_tickers.side_effect = lambda sym: [{"lastPrice": "1.0000"}]
    mock_bot.client.get_open_orders.return_value = []
    mock_bot.guard.update_market_state = MagicMock(return_value=(False, "", {}))

    mock_bot.step()

    assert mock_bot.trio_mode_active is False
    assert mock_bot.dual_mode_active is True
    assert "Dual" in mock_bot.stats["portfolio_mode"]


def test_cancel_all_portfolio_buys_covers_all_three(mock_bot):
    mock_bot.client.get_open_orders.side_effect = lambda sym: [
        {"orderId": f"buy_{sym}", "side": "Buy", "price": "1.0"}
    ]
    mock_bot.cancel_all_portfolio_buys()

    canceled_symbols = [c[0][0] for c in mock_bot.client.cancel_order.call_args_list]
    assert PRIMARY_SYMBOL in canceled_symbols
    assert SECONDARY_SYMBOL in canceled_symbols
    assert TERTIARY_SYMBOL in canceled_symbols
