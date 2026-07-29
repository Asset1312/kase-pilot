"""Application composition functions."""

from __future__ import annotations

from tradernet import Tradernet

from kase_pilot.application import (
    FindInstrument,
    GetAccountSummary,
    GetCurrentQuotes,
    GetHistoricalCandles,
    GetNews,
    GetPlacedOrders,
    GetSecurityInfo,
    GetTradesHistory,
    GetUserInfo,
)
from kase_pilot.broker import AccountService, MarketService
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter


def create_get_account_summary(
    public_key: str,
    private_key: str,
) -> GetAccountSummary:
    """Build the object graph for the account-summary use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetAccountSummary(account_service)


def create_find_instrument(
    public_key: str,
    private_key: str,
) -> FindInstrument:
    """Build the object graph for the instrument-search use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return FindInstrument(market_service)


def create_get_current_quotes(
    public_key: str,
    private_key: str,
) -> GetCurrentQuotes:
    """Build the object graph for the current-quotes use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetCurrentQuotes(market_service)


def create_get_historical_candles(
    public_key: str,
    private_key: str,
) -> GetHistoricalCandles:
    """Build the object graph for the historical-candles use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetHistoricalCandles(market_service)


def create_get_news(
    public_key: str,
    private_key: str,
) -> GetNews:
    """Build the object graph for the news use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetNews(market_service)


def create_get_placed_orders(
    public_key: str,
    private_key: str,
) -> GetPlacedOrders:
    """Build the object graph for the placed-orders use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetPlacedOrders(account_service)


def create_get_security_info(
    public_key: str,
    private_key: str,
) -> GetSecurityInfo:
    """Build the object graph for the instrument-information use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetSecurityInfo(market_service)


def create_get_trades_history(
    public_key: str,
    private_key: str,
) -> GetTradesHistory:
    """Build the object graph for the trades-history use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetTradesHistory(account_service)


def create_get_user_info(
    public_key: str,
    private_key: str,
) -> GetUserInfo:
    """Build the object graph for the user-information use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetUserInfo(account_service)
