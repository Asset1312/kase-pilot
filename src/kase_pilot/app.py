"""Application composition functions."""

from __future__ import annotations

from tradernet import Tradernet

from kase_pilot.application import GetCurrentQuotes, GetSecurityInfo
from kase_pilot.broker import MarketService
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter


def create_get_current_quotes(
    public_key: str,
    private_key: str,
) -> GetCurrentQuotes:
    """Build the object graph for the current-quotes use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetCurrentQuotes(market_service)


def create_get_security_info(
    public_key: str,
    private_key: str,
) -> GetSecurityInfo:
    """Build the object graph for the instrument-information use case."""
    sdk_client = Tradernet(public_key, private_key)
    adapter = TradernetSdkAdapter(sdk_client)
    market_service = MarketService(adapter)
    return GetSecurityInfo(market_service)
