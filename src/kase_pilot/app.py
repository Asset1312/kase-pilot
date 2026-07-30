"""Application composition functions."""

from __future__ import annotations

from tradernet import Tradernet

from kase_pilot.application import (
    ExportSecurities,
    FindInstrument,
    GetAccountSummary,
    GetBrokerReport,
    GetCorporateActions,
    GetCurrentQuotes,
    GetHistorical,
    GetHistoricalCandles,
    GetMarketStatus,
    GetMostTraded,
    GetNews,
    GetOptions,
    GetOrderFiles,
    GetPlacedOrders,
    GetPriceAlerts,
    GetRequestsHistory,
    GetSecurityInfo,
    GetSymbol,
    GetSymbols,
    GetTariffs,
    GetTradesHistory,
    GetUserInfo,
    ListSecuritySessions,
)
from kase_pilot.broker import AccountService, MarketService
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter


def create_export_securities(
    public_key: str,
    private_key: str,
) -> ExportSecurities:
    """Build the object graph for the securities-export use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return ExportSecurities(market_service)


def create_get_account_summary(
    public_key: str,
    private_key: str,
) -> GetAccountSummary:
    """Build the object graph for the account-summary use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetAccountSummary(account_service)


def create_get_broker_report(
    public_key: str,
    private_key: str,
) -> GetBrokerReport:
    """Build the object graph for the broker-report use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetBrokerReport(market_service)


def create_get_corporate_actions(
    public_key: str,
    private_key: str,
) -> GetCorporateActions:
    """Build the object graph for the corporate-actions use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetCorporateActions(market_service)


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


def create_get_historical(
    public_key: str,
    private_key: str,
) -> GetHistorical:
    """Build the object graph for the historical-orders use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetHistorical(market_service)


def create_get_historical_candles(
    public_key: str,
    private_key: str,
) -> GetHistoricalCandles:
    """Build the object graph for the historical-candles use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetHistoricalCandles(market_service)


def create_get_market_status(
    public_key: str,
    private_key: str,
) -> GetMarketStatus:
    """Build the object graph for the market-status use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetMarketStatus(market_service)


def create_get_most_traded(
    public_key: str,
    private_key: str,
) -> GetMostTraded:
    """Build the object graph for the most-traded use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetMostTraded(market_service)


def create_get_news(
    public_key: str,
    private_key: str,
) -> GetNews:
    """Build the object graph for the news use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetNews(market_service)


def create_get_options(
    public_key: str,
    private_key: str,
) -> GetOptions:
    """Build the object graph for the options use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetOptions(market_service)


def create_get_order_files(
    public_key: str,
    private_key: str,
) -> GetOrderFiles:
    """Build the object graph for the order-files use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetOrderFiles(market_service)


def create_get_placed_orders(
    public_key: str,
    private_key: str,
) -> GetPlacedOrders:
    """Build the object graph for the placed-orders use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    account_service = AccountService(adapter)
    return GetPlacedOrders(account_service)


def create_get_price_alerts(
    public_key: str,
    private_key: str,
) -> GetPriceAlerts:
    """Build the object graph for the price-alerts use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetPriceAlerts(market_service)


def create_get_requests_history(
    public_key: str,
    private_key: str,
) -> GetRequestsHistory:
    """Build the object graph for the requests-history use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetRequestsHistory(market_service)


def create_get_security_info(
    public_key: str,
    private_key: str,
) -> GetSecurityInfo:
    """Build the object graph for the instrument-information use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetSecurityInfo(market_service)


def create_list_security_sessions(
    public_key: str,
    private_key: str,
) -> ListSecuritySessions:
    """Build the object graph for the security-sessions use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return ListSecuritySessions(market_service)


def create_get_symbols(
    public_key: str,
    private_key: str,
) -> GetSymbols:
    """Build the object graph for the symbols use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetSymbols(market_service)


def create_get_symbol(
    public_key: str,
    private_key: str,
) -> GetSymbol:
    """Build the object graph for the symbol use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetSymbol(market_service)


def create_get_tariffs(
    public_key: str,
    private_key: str,
) -> GetTariffs:
    """Build the object graph for the tariffs use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetTariffs(market_service)


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
