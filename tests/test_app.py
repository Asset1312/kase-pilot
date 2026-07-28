"""Tests for application composition."""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from kase_pilot import app
from kase_pilot.application import (
    FindInstrument,
    GetCurrentQuotes,
    GetHistoricalCandles,
    GetSecurityInfo,
)
from kase_pilot.broker import MarketService
from kase_pilot.broker._tradernet_sdk import TradernetSdkAdapter


class FakeSdkClient:
    pass


def test_create_find_instrument_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_find_instrument("public-value", "private-value")

    assert isinstance(use_case, FindInstrument)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_instrument_search_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def find_symbol(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_find_instrument("public-value", "private-value")


def test_instrument_search_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_find_instrument("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_current_quotes_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_current_quotes("public-value", "private-value")

    assert isinstance(use_case, GetCurrentQuotes)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_current_quotes_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_quotes(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_current_quotes("public-value", "private-value")


def test_current_quotes_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_current_quotes("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_historical_candles_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_historical_candles(
        "public-value",
        "private-value",
    )

    assert isinstance(use_case, GetHistoricalCandles)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_historical_candles_composition_does_not_execute_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def get_candles(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_historical_candles("public-value", "private-value")


def test_historical_candles_composition_error_propagates_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = RuntimeError("SDK client construction failed")

    def fail_sdk_client(public: str, private: str) -> None:
        raise original

    monkeypatch.setattr(app, "Tradernet", fail_sdk_client)

    with pytest.raises(RuntimeError) as exc_info:
        app.create_get_historical_candles("public-value", "private-value")

    assert exc_info.value is original


def test_create_get_security_info_builds_expected_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    sdk_client = FakeSdkClient()

    def create_sdk_client(public: str, private: str) -> FakeSdkClient:
        calls.append((public, private))
        return sdk_client

    monkeypatch.setattr(app, "Tradernet", create_sdk_client)

    use_case = app.create_get_security_info("public-value", "private-value")

    assert isinstance(use_case, GetSecurityInfo)
    market_service = use_case._market_service
    assert isinstance(market_service, MarketService)
    adapter = market_service._adapter
    assert isinstance(adapter, TradernetSdkAdapter)
    assert adapter._client is sdk_client
    assert calls == [("public-value", "private-value")]


def test_composition_does_not_call_sdk_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NetworkGuardSdkClient:
        def security_info(self, *args: object, **kwargs: object) -> Any:
            raise AssertionError("SDK operation must not run during composition")

    monkeypatch.setattr(
        app, "Tradernet", lambda public, private: NetworkGuardSdkClient()
    )

    app.create_get_security_info("public-value", "private-value")


def test_each_call_builds_a_separate_object_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app, "Tradernet", lambda public, private: FakeSdkClient())

    first = app.create_get_security_info("public-value", "private-value")
    second = app.create_get_security_info("public-value", "private-value")

    assert first is not second
    assert first._market_service is not second._market_service
    assert first._market_service._adapter is not second._market_service._adapter
    assert (
        first._market_service._adapter._client
        is not second._market_service._adapter._client
    )


def test_private_key_is_absent_from_composed_object_reprs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_key = "private-secret-value"
    monkeypatch.setattr(app, "Tradernet", lambda public, private: FakeSdkClient())

    use_case = app.create_get_security_info("public-value", private_key)
    market_service = use_case._market_service
    adapter = market_service._adapter

    assert private_key not in repr(use_case)
    assert private_key not in repr(market_service)
    assert private_key not in repr(adapter)


def test_app_module_has_no_environment_cli_or_process_boundary_imports() -> None:
    tree = ast.parse(inspect.getsource(app))
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "os" not in imported_modules
    assert "kase_pilot.main" not in imported_modules
    assert "kase_pilot.cli" not in imported_modules
    assert "main" not in imported_names
    assert "run" not in imported_names
