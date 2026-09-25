"""Bybit Kazakhstan Spot V5 Lightweight REST Client.

Supports HMAC-SHA256 signature authentication, wallet balance inspection,
limit order placement (Maker), order cancellation, and execution/fee tracking.
Uses requests.Session with browser-grade TLS headers to reliably pass Cloudflare.
"""

from __future__ import annotations

import os
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("BybitV5Client")


class BybitV5Client:
    """Lightweight Bybit V5 REST Client for Bybit Kazakhstan."""

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        domain: str = "api.bybit.kz",
        recv_window: int = 5000,
    ) -> None:
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.domain = domain.strip()
        self.recv_window = str(recv_window)
        self.base_url = f"https://{self.domain}"
        self.session = requests.Session()
        proxy = os.environ.get("BYBIT_PROXY", os.environ.get("HTTPS_PROXY", "")).strip()
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        })

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def _generate_signature(self, timestamp: str, payload_str: str) -> str:
        """Bybit V5 HMAC-SHA256 signature generator."""
        param_str = f"{timestamp}{self.api_key}{self.recv_window}{payload_str}"
        return hmac.new(
            self.api_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 8,
    ) -> Dict[str, Any]:
        """Executes signed or public HTTP request to Bybit Kazakhstan V5 API."""
        if not self.is_configured:
            return {"retCode": -1, "retMsg": "API credentials not configured", "result": {}}

        timestamp = str(int(time.time() * 1000))
        url = f"{self.base_url}{endpoint}"
        payload_str = ""

        if method.upper() == "GET":
            if params:
                query_str = urllib.parse.urlencode(sorted(params.items()))
                url = f"{url}?{query_str}"
                payload_str = query_str
        elif method.upper() == "POST":
            payload_str = json.dumps(data) if data else ""

        signature = self._generate_signature(timestamp, payload_str)

        headers = {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
        }

        try:
            if method.upper() == "GET":
                resp = self.session.get(url, headers=headers, timeout=timeout)
            else:
                resp = self.session.post(url, data=payload_str.encode("utf-8"), headers=headers, timeout=timeout)

            if resp.status_code == 403:
                return {
                    "retCode": 403,
                    "retMsg": "WAF_IP_BLOCKED: Облачный IP (Render/AWS) заблокирован Bybit WAF (Tencent Cloud EdgeOne)",
                    "result": {}
                }

            try:
                body_json = resp.json()
                return body_json
            except Exception:
                return {"retCode": resp.status_code, "retMsg": resp.text[:200], "result": {}}

        except Exception as e:
            logger.error(f"Bybit request failed [{endpoint}]: {e}")
            return {"retCode": -1, "retMsg": str(e), "result": {}}

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Fetches wallet balance for specified account type (UNIFIED)."""
        res = self._request("GET", "/v5/account/wallet-balance", params={"accountType": account_type})

        summary = {
            "retCode": res.get("retCode", -1),
            "retMsg": res.get("retMsg", ""),
            "key_len": len(self.api_key),
            "secret_len": len(self.api_secret),
            "key_prefix": self.api_key[:6] if len(self.api_key) >= 6 else "",
            "total_usd": 0.0,
            "available_usdt": 0.0,
            "locked_usdt": 0.0,
            "coins": {},
        }

        if res.get("retCode") == 0:
            acc_list = res.get("result", {}).get("list", [])
            for acc in acc_list:
                coin_list = acc.get("coin", [])
                for c in coin_list:
                    coin_name = c.get("coin", "")
                    wallet_bal = float(c.get("walletBalance") or 0.0)
                    locked = float(c.get("locked") or 0.0)
                    free = float(c.get("availableToWithdraw") or c.get("free") or (wallet_bal - locked))
                    summary["coins"][coin_name] = {
                        "balance": wallet_bal,
                        "free": max(0.0, free),
                        "locked": max(0.0, locked),
                    }
                    if coin_name == "USDT":
                        summary["available_usdt"] += max(0.0, free)
                        summary["locked_usdt"] += max(0.0, locked)
                        summary["total_usd"] += wallet_bal
        return summary

    def create_limit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        category: str = "spot",
        post_only: bool = True,
        qty_precision: int = 2,
        price_precision: int = 4,
        order_link_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Places a limit Maker order on Bybit Spot with PostOnly support."""
        data = {
            "category": category,
            "symbol": symbol.upper(),
            "side": side.capitalize(),  # "Buy" or "Sell"
            "orderType": "Limit",
            "qty": f"{qty:.{qty_precision}f}",
            "price": f"{price:.{price_precision}f}",
            "timeInForce": "PostOnly" if post_only else "GTC",
        }
        if order_link_id:
            data["orderLinkId"] = order_link_id
        return self._request("POST", "/v5/order/create", data=data)

    def amend_order(
        self,
        symbol: str,
        order_id: Optional[str] = None,
        order_link_id: Optional[str] = None,
        price: Optional[float] = None,
        qty: Optional[float] = None,
        category: str = "spot",
        price_precision: int = 4,
        qty_precision: int = 2,
    ) -> Dict[str, Any]:
        """Amends an existing limit order on Bybit Spot without cancelling it."""
        data: Dict[str, Any] = {
            "category": category,
            "symbol": symbol.upper(),
        }
        if order_id:
            data["orderId"] = order_id
        if order_link_id:
            data["orderLinkId"] = order_link_id
        if price is not None:
            data["price"] = f"{price:.{price_precision}f}"
        if qty is not None:
            data["qty"] = f"{qty:.{qty_precision}f}"
        return self._request("POST", "/v5/order/amend", data=data)

    def create_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        category: str = "spot",
        qty_precision: int = 2,
    ) -> Dict[str, Any]:
        """Places a market Taker order on Bybit Spot for immediate execution."""
        data = {
            "category": category,
            "symbol": symbol.upper(),
            "side": side.capitalize(),
            "orderType": "Market",
            "qty": f"{qty:.{qty_precision}f}",
        }
        if category == "spot" and side.capitalize() == "Buy":
            data["marketUnit"] = "baseCoin"
        return self._request("POST", "/v5/order/create", data=data)

    def cancel_order(self, symbol: str, order_id: str, category: str = "spot") -> Dict[str, Any]:
        """Cancels an active order by orderId."""
        data = {
            "category": category,
            "symbol": symbol.upper(),
            "orderId": order_id,
        }
        return self._request("POST", "/v5/order/cancel", data=data)

    def get_open_orders(self, symbol: str, category: str = "spot") -> List[Dict[str, Any]]:
        """Fetches active resting orders for symbol."""
        res = self._request("GET", "/v5/order/realtime", params={"category": category, "symbol": symbol.upper()})
        if res.get("retCode") == 0:
            return res.get("result", {}).get("list", [])
        return []

    def get_execution_history(self, symbol: str, category: str = "spot", limit: int = 20) -> List[Dict[str, Any]]:
        """Fetches recent execution records including trading fees."""
        res = self._request(
            "GET",
            "/v5/execution/list",
            params={"category": category, "symbol": symbol.upper(), "limit": limit},
        )
        if res.get("retCode") == 0:
            return res.get("result", {}).get("list", [])
        return []
