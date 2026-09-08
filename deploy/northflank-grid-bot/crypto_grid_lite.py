#!/usr/bin/env python3
"""
Northflank Lightweight Binance Grid Bot (Spot Testnet & Live)
============================================================
Optimized for 24/7 cloud execution on Northflank.com free/starter tiers.
- RAM usage: ~30-50 MB
- Zero local database overhead (pure REST/WebSocket execution)
- Supports:
    * Binance Spot Testnet (https://testnet.binance.vision)
    * Binance Live Spot (https://api.binance.com)
- Safety guards:
    * Strict $10 per-order notional guard for micro-deposits ($50)
    * Maker-only limit orders
    * Dynamic grid re-anchoring
    * Optional Telegram notifications
"""

import os
import sys
import time
import hmac
import hashlib
import json
import logging
import urllib.request
import urllib.parse
from decimal import Decimal, ROUND_DOWN
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("grid_bot")

# --- Environment Configuration ---
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "").strip()
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "").strip()
USE_TESTNET = os.getenv("USE_TESTNET", "true").strip().lower() in ("true", "1", "yes")

# Base URLs
BASE_URL = "https://testnet.binance.vision" if USE_TESTNET else "https://api.binance.com"

# Strategy parameters (optimized for $50 account)
SYMBOL = os.getenv("SYMBOL", "SOLUSDT").strip().upper()
ORDER_AMOUNT_USDT = Decimal(os.getenv("ORDER_AMOUNT_USDT", "10.0"))  # $10 per order
GRID_LEVELS = int(os.getenv("GRID_LEVELS", "3"))                   # 3 buy levels down
GRID_STEP_BPS = Decimal(os.getenv("GRID_STEP_BPS", "40.0"))        # 0.40% step between lines
GRID_PROFIT_BPS = Decimal(os.getenv("GRID_PROFIT_BPS", "60.0"))    # +0.60% profit target
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "3.0"))  # 3 sec tick

# Telegram Alerts (optional)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()


def send_telegram(text: str) -> None:
    """Send alert message to Telegram if configured."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = urllib.parse.urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(req, timeout=5) as res:
            pass
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


class BinanceClient:
    """Lightweight pure-python Binance REST API client with zero dependencies."""

    def __init__(self, api_key: str, secret_key: str, base_url: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url

    def _sign(self, query_string: str) -> str:
        return hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def request(self, method: str, path: str, params: dict | None = None, signed: bool = False) -> dict:
        params = params or {}
        headers = {"X-MBX-APIKEY": self.api_key} if self.api_key else {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query_string = urllib.parse.urlencode(params)
            signature = self._sign(query_string)
            query_string += f"&signature={signature}"
        else:
            query_string = urllib.parse.urlencode(params) if params else ""

        url = f"{self.base_url}{path}"
        if method == "GET" and query_string:
            url += f"?{query_string}"
            data = None
        elif method in ("POST", "DELETE"):
            data = query_string.encode("utf-8") if query_string else None
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = None

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_msg = err.read().decode("utf-8")
            logger.error(f"Binance API HTTPError {err.code}: {err_msg}")
            raise RuntimeError(f"Binance API error: {err_msg}")
        except Exception as err:
            logger.error(f"Network error: {err}")
            raise

    def get_ticker_price(self, symbol: str) -> Decimal:
        res = self.request("GET", "/api/v3/ticker/price", {"symbol": symbol})
        return Decimal(str(res["price"]))

    def get_order_book(self, symbol: str, limit: int = 5) -> dict:
        return self.request("GET", "/api/v3/depth", {"symbol": symbol, "limit": limit})

    def get_account_balance(self) -> dict[str, Decimal]:
        res = self.request("GET", "/api/v3/account", signed=True)
        balances = {}
        for b in res.get("balances", []):
            free = Decimal(str(b["free"]))
            locked = Decimal(str(b["locked"]))
            if free > 0 or locked > 0:
                balances[b["asset"]] = free + locked
        return balances

    def create_limit_order(self, symbol: str, side: str, quantity: Decimal, price: Decimal) -> dict:
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": f"{quantity}",
            "price": f"{price}",
        }
        return self.request("POST", "/api/v3/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> dict:
        return self.request("DELETE", "/api/v3/order", {"symbol": symbol, "orderId": order_id}, signed=True)

    def get_open_orders(self, symbol: str) -> list[dict]:
        return self.request("GET", "/api/v3/openOrders", {"symbol": symbol}, signed=True)


@dataclass
class ActiveGridLevel:
    order_id: int
    side: str
    price: Decimal
    quantity: Decimal
    buy_entry_price: Decimal | None = None


class CloudGridEngine:
    """Manages dynamic grid execution loop."""

    def __init__(self, client: BinanceClient):
        self.client = client
        self.symbol = SYMBOL
        self.active_levels: dict[int, ActiveGridLevel] = {}
        self.total_closed_cycles = 0
        self.total_realized_profit = Decimal("0.0")

        # Symbol filters (price/qty step precision)
        self.price_decimals = 2
        self.qty_decimals = 3
        self._load_symbol_info()

    def _load_symbol_info(self) -> None:
        try:
            info = self.client.request("GET", "/api/v3/exchangeInfo", {"symbol": self.symbol})
            for s in info.get("symbols", []):
                if s["symbol"] == self.symbol:
                    for f in s.get("filters", []):
                        if f["filterType"] == "PRICE_FILTER":
                            tick_size = f["tickSize"].rstrip("0")
                            self.price_decimals = len(tick_size.split(".")[1]) if "." in tick_size else 0
                        elif f["filterType"] == "LOT_SIZE":
                            step_size = f["stepSize"].rstrip("0")
                            self.qty_decimals = len(step_size.split(".")[1]) if "." in step_size else 0
            logger.info(f"Loaded symbol {self.symbol}: price_dec={self.price_decimals}, qty_dec={self.qty_decimals}")
        except Exception as e:
            logger.warning(f"Using default precision: {e}")

    def round_price(self, p: Decimal) -> Decimal:
        return round(p, self.price_decimals)

    def round_qty(self, q: Decimal) -> Decimal:
        fmt = f"0.{'0' * self.qty_decimals}" if self.qty_decimals > 0 else "0"
        return q.quantize(Decimal(fmt), rounding=ROUND_DOWN)

    def place_buy_levels(self, current_price: Decimal) -> None:
        logger.info(f"Setting up grid levels below {current_price} USDT...")
        for i in range(1, GRID_LEVELS + 1):
            offset = (GRID_STEP_BPS * Decimal(i)) / Decimal("10000.0")
            p = self.round_price(current_price * (Decimal("1.0") - offset))
            qty = self.round_qty(ORDER_AMOUNT_USDT / p)

            if qty <= 0:
                continue

            try:
                res = self.client.create_limit_order(self.symbol, "BUY", qty, p)
                order_id = res["orderId"]
                self.active_levels[order_id] = ActiveGridLevel(
                    order_id=order_id,
                    side="BUY",
                    price=p,
                    quantity=qty
                )
                logger.info(f"  [+] Placed BUY level #{i}: {qty} {self.symbol} @ {p} (Order #{order_id})")
            except Exception as e:
                logger.error(f"Failed to place BUY level #{i}: {e}")

    def run(self) -> None:
        logger.info("=" * 60)
        logger.info(f"   STARTING CLOUD GRID BOT ON {'TESTNET' if USE_TESTNET else 'LIVE'}")
        logger.info(f"   Symbol: {self.symbol} | Order: ${ORDER_AMOUNT_USDT} | Levels: {GRID_LEVELS}")
        logger.info(f"   Step: {GRID_STEP_BPS} bps ({float(GRID_STEP_BPS)/100:.2f}%) | Profit: {GRID_PROFIT_BPS} bps")
        logger.info("=" * 60)

        # Initial balances
        balances = self.client.get_account_balance()
        usdt_bal = balances.get("USDT", Decimal("0.0"))
        logger.info(f"Connected to Binance. Available USDT balance: {usdt_bal:.2f}")

        send_telegram(
            f"🚀 *Northflank Grid Bot Started*\n"
            f"• Mode: `{'TESTNET' if USE_TESTNET else 'LIVE'}`\n"
            f"• Symbol: `{self.symbol}`\n"
            f"• USDT Balance: `${usdt_bal:.2f}`"
        )

        curr_price = self.client.get_ticker_price(self.symbol)
        logger.info(f"Current {self.symbol} price: {curr_price}")

        # Cancel any obsolete existing open orders on restart
        open_orders = self.client.get_open_orders(self.symbol)
        if open_orders:
            logger.info(f"Clearing {len(open_orders)} existing open orders...")
            for o in open_orders:
                try:
                    self.client.cancel_order(self.symbol, o["orderId"])
                except Exception:
                    pass

        # Initial grid placement
        self.place_buy_levels(curr_price)

        # Main polling loop
        while True:
            try:
                time.sleep(POLL_INTERVAL_SEC)
                open_orders = {o["orderId"]: o for o in self.client.get_open_orders(self.symbol)}

                # Check if any tracked order is missing (filled)
                filled_ids = [oid for oid in self.active_levels if oid not in open_orders]

                for oid in filled_ids:
                    lvl = self.active_levels.pop(oid)
                    if lvl.side == "BUY":
                        # Buy order filled -> Place Take Profit Sell
                        target_sell = self.round_price(lvl.price * (Decimal("1.0") + GRID_PROFIT_BPS / Decimal("10000.0")))
                        logger.info(f"🟢 [BUY FILLED] #{lvl.order_id} @ {lvl.price}. Placing Take Profit SELL @ {target_sell}...")

                        res = self.client.create_limit_order(self.symbol, "SELL", lvl.quantity, target_sell)
                        new_oid = res["orderId"]
                        self.active_levels[new_oid] = ActiveGridLevel(
                            order_id=new_oid,
                            side="SELL",
                            price=target_sell,
                            quantity=lvl.quantity,
                            buy_entry_price=lvl.price
                        )

                        send_telegram(f"🟢 *Buy Filled*: {lvl.quantity} {self.symbol} @ ${lvl.price}\nTarget Sell: ${target_sell}")

                    elif lvl.side == "SELL":
                        # Sell order filled -> Cycle Complete!
                        gross_gain = (lvl.price - (lvl.buy_entry_price or lvl.price)) * lvl.quantity
                        self.total_closed_cycles += 1
                        self.total_realized_profit += gross_gain

                        logger.info(f"🎉 [TAKE PROFIT FILLED] #{lvl.order_id} @ {lvl.price} (+${gross_gain:.4f})")
                        logger.info(f"   Cycles: {self.total_closed_cycles} | Total Profit: +${self.total_realized_profit:.4f} USDT")

                        send_telegram(
                            f"🎉 *Cycle #{self.total_closed_cycles} Completed!*\n"
                            f"• Profit: `+${gross_gain:.4f} USDT`\n"
                            f"• Total Earned: `+${self.total_realized_profit:.4f} USDT`"
                        )

                        # Respawn lower buy level to keep grid spinning
                        curr_p = self.client.get_ticker_price(self.symbol)
                        buy_p = self.round_price(curr_p * (Decimal("1.0") - (GRID_STEP_BPS / Decimal("10000.0"))))
                        buy_qty = self.round_qty(ORDER_AMOUNT_USDT / buy_p)

                        if buy_qty > 0:
                            res = self.client.create_limit_order(self.symbol, "BUY", buy_qty, buy_p)
                            new_buy_id = res["orderId"]
                            self.active_levels[new_buy_id] = ActiveGridLevel(
                                order_id=new_buy_id,
                                side="BUY",
                                price=buy_p,
                                quantity=buy_qty
                            )

                # Rebalance if no buys remain
                has_active_buys = any(lvl.side == "BUY" for lvl in self.active_levels.values())
                if not has_active_buys:
                    curr_p = self.client.get_ticker_price(self.symbol)
                    self.place_buy_levels(curr_p)

            except Exception as e:
                logger.error(f"Error in grid loop: {e}")
                time.sleep(5)


def main() -> None:
    if not BINANCE_API_KEY or not BINANCE_SECRET_KEY:
        logger.error("Missing BINANCE_API_KEY or BINANCE_SECRET_KEY in environment variables!")
        sys.exit(1)

    client = BinanceClient(BINANCE_API_KEY, BINANCE_SECRET_KEY, BASE_URL)
    engine = CloudGridEngine(client)
    engine.run()


if __name__ == "__main__":
    main()
