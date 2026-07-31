"""End-to-end tests for symbols/instruments against the real bundled catalog.

Unlike tests/test_main.py, these do not monkeypatch create_get_symbols or
create_get_instruments: they exercise the real composition and the real
packaged instruments.json, to catch mismatches between the catalog's
exchange/market values and what the CLI actually filters by.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from kase_pilot import main as main_module


def _tickers(payload: object) -> set[str]:
    if isinstance(payload, dict):
        entries: Any = payload["symbols"]
    else:
        entries = payload
    return {entry["ticker"] for entry in entries}


def test_symbols_by_exchange_returns_halyk_bank(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main_module.run("symbols", exchange="KASE", environ={})

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "HSBK.KZ" in _tickers(output)


def test_symbols_exchange_filter_is_case_insensitive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main_module.run("symbols", exchange="kase", environ={})

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "HSBK.KZ" in _tickers(output)


def test_instruments_by_market_returns_halyk_bank(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main_module.run("instruments", market="KASE_STOCK", environ={})

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "HSBK.KZ" in _tickers(output)


def test_instruments_market_filter_is_case_insensitive(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main_module.run("instruments", market="kase_stock", environ={})

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "HSBK.KZ" in _tickers(output)


def test_instruments_show_expired_flag_is_plumbed_through(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main_module.run(
        "instruments",
        market="KASE_STOCK",
        show_expired=True,
        environ={},
    )

    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert "HSBK.KZ" in _tickers(output)


def test_symbols_requires_no_broker_credentials(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # environ={} deliberately contains no TRADERNET_* variables: symbols is
    # an offline command and must not require broker credentials.
    assert main_module.run("symbols", environ={}) == 0


def test_instruments_requires_no_broker_credentials(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main_module.run("instruments", market="KASE_STOCK", environ={}) == 0
