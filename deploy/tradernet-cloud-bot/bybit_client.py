"""Bybit Kazakhstan / Global Spot V5 Lightweight REST Client.

Supports HMAC-SHA256 signature authentication, wallet balance inspection,
limit order placement (Maker), order cancellation, and execution/fee tracking.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger("BybitV5Client")


class BybitV5Client:
    """Lightweight Bybit V5 REST Client with zero heavy external dependencies."""

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

    @property
    def is_configured(self) -> bool:
        """Returns True if API key and secret are provided."""
        return bool(self.api_key and self.api_secret)

    def _generate_signature(self, timestamp: str, payload_str: str) -> str:
        """Generates HMAC-SHA256 signature according to Bybit V5 specification."""
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
        """Executes signed or public HTTP request to Bybit V5 API."""
        if not self.is_configured:
            return {"retCode": -1, "retMsg": "API credentials not configured", "result": {}}

        timestamp = str(int(time.time() * 1000))
        url = f"{self.base_url}{endpoint}"
        body_bytes = None
        payload_str = ""

        if method.upper() == "GET":
            if params:
                query_str = urllib.parse.urlencode(sorted(params.items()))
                url = f"{url}?{query_str}"
                payload_str = query_str
        elif method.upper() == "POST":
            payload_str = json.dumps(data) if data else ""
            body_bytes = payload_str.encode("utf-8")

        signature = self._generate_signature(timestamp, payload_str)

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-BAPI-API-KEY": self.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self.recv_window,
        }

        try:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method.upper())
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            logger.error(f"Bybit API HTTP {he.code} Error [{endpoint}]: {err_body}")
            # If regional api.bybit.kz returned 403 (datacenter filter), try api.bybit.com fallback
            if he.code == 403 and "bybit.kz" in self.base_url:
                try:
                    fallback_url = url.replace("api.bybit.kz", "api.bybit.com")
                    req_fb = urllib.request.Request(fallback_url, data=body_bytes, headers=headers, method=method.upper())
                    with urllib.request.urlopen(req_fb, timeout=timeout) as fb_resp:
                        raw = fb_resp.read().decode("utf-8")
                        return json.loads(raw)
                except Exception:
                    pass
            try:
                return json.loads(err_body)
            except Exception:
                return {"retCode": he.code, "retMsg": str(he), "result": {}}
        except Exception as e:
            logger.error(f"Bybit request failed [{endpoint}]: {e}")
            return {"retCode": -1, "retMsg": str(e), "result": {}}

    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """Fetches wallet balance for specified account type (UNIFIED, SPOT)."""
        res = self._request("GET", "/v5/account/wallet-balance", params={"accountType": account_type})
        if res.get("retCode") != 0 and account_type == "UNIFIED":
            # Fallback to SPOT if account is classic spot
            res = self._request("GET", "/v5/account/wallet-balance", params={"accountType": "SPOT"})

        summary = {
            "retCode": res.get("retCode", -1),
            "retMsg": res.get("retMsg", ""),
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
    ) -> Dict[str, Any]:
        """Places a limit Maker order on Bybit Spot."""
        data = {
            "category": category,
            "symbol": symbol.upper(),
            "side": side.capitalize(),  # "Buy" or "Sell"
            "orderType": "Limit",
            "qty": str(qty),
            "price": str(price),
            "timeInForce": "GTC",
        }
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
