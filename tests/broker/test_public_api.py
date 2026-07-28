"""Tests for the public surface of :mod:`kase_pilot.broker`."""

import pytest

from kase_pilot import broker
from kase_pilot.broker import (
    AccountService,
    BrokerClient,
    MarketService,
    OrdersService,
    PortfolioService,
    ReportsService,
)
from kase_pilot.broker.account import AccountService as ModuleAccountService
from kase_pilot.broker.client import BrokerClient as ModuleBrokerClient
from kase_pilot.broker.market import MarketService as ModuleMarketService
from kase_pilot.broker.orders import OrdersService as ModuleOrdersService
from kase_pilot.broker.portfolio import PortfolioService as ModulePortfolioService
from kase_pilot.broker.reports import ReportsService as ModuleReportsService


def test_broker_package_imports_successfully() -> None:
    assert broker is not None


def test_public_classes_import_successfully() -> None:
    assert all(
        symbol is not None
        for symbol in (
            AccountService,
            BrokerClient,
            MarketService,
            OrdersService,
            PortfolioService,
            ReportsService,
        )
    )


def test_all_contains_exactly_current_public_exports() -> None:
    assert set(broker.__all__) == {
        "AccountService",
        "BrokerClient",
        "MarketService",
        "OrdersService",
        "PortfolioService",
        "ReportsService",
    }
    assert len(broker.__all__) == 6


@pytest.mark.parametrize(
    ("exported", "module_class"),
    [
        (AccountService, ModuleAccountService),
        (BrokerClient, ModuleBrokerClient),
        (MarketService, ModuleMarketService),
        (OrdersService, ModuleOrdersService),
        (PortfolioService, ModulePortfolioService),
        (ReportsService, ModuleReportsService),
    ],
)
def test_exported_symbol_is_source_module_class(
    exported: type[object],
    module_class: type[object],
) -> None:
    assert exported is module_class


@pytest.mark.parametrize(
    "name",
    [
        "SecuritySession",
        "AuthProvider",
        "HttpTransport",
        "JsonValue",
        "RawPayload",
    ],
)
def test_internal_symbols_are_not_exported(name: str) -> None:
    assert name not in broker.__all__
    assert not hasattr(broker, name)
