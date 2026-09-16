"""Unit tests for BybitV5Client."""

import json
import sys
from pathlib import Path
import pytest

# Add deploy/tradernet-cloud-bot to path
PILOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PILOT_DIR / "deploy" / "tradernet-cloud-bot"))

from bybit_client import BybitV5Client


def test_bybit_client_unconfigured():
    client = BybitV5Client(api_key="", api_secret="")
    assert not client.is_configured
    res = client.get_wallet_balance()
    assert res["retCode"] == -1
    assert "not configured" in res["retMsg"]


def test_bybit_client_signature_generation():
    client = BybitV5Client(api_key="my_key", api_secret="my_secret")
    assert client.is_configured
    sig = client._generate_signature(timestamp="1700000000000", payload_str="symbol=SUIUSDT")
    assert len(sig) == 64
    assert isinstance(sig, str)


def test_bybit_client_order_payload():
    client = BybitV5Client(api_key="my_key", api_secret="my_secret")
    # Calling create_limit_order against invalid domain will fail gracefully
    res = client.create_limit_order("SUIUSDT", "Buy", 3.0, 0.70)
    assert "retCode" in res
