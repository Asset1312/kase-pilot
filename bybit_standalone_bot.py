#!/usr/bin/env python3
"""
Bybit Kazakhstan Spot V5 Standalone Micro-Grid Scalper.
Engineered for 24/7 autonomous operation on Android (Termux) / Linux / Windows.
Strictly isolated to Bybit Kazakhstan (api.bybit.kz) - Zero Tradernet/KASE overhead.
"""

from __future__ import annotations

import datetime
import http.server
import json
import logging
import math
import os
import socketserver
import sys
import threading
import time
from typing import Any, Dict, List, Optional
import urllib.request
import dotenv

# Load environment variables (.env)
dotenv.load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("BybitBot")

# Ensure bybit_client import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOY_DIR = os.path.join(SCRIPT_DIR, "deploy", "tradernet-cloud-bot")
if DEPLOY_DIR not in sys.path:
    sys.path.insert(0, DEPLOY_DIR)

try:
    from bybit_client import BybitV5Client
except ImportError:
    from deploy.tradernet_cloud_bot.bybit_client import BybitV5Client

# Credentials & Telegram
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
PORT = int(os.getenv("PORT", "8080"))

# Micro-Grid Configuration ($10.73 deposit optimized)
SYMBOL = "SUIUSDT"
GRID_CONFIG = {
    "step_1": {"discount": 0.0055, "alloc": 5.10, "tp": 0.0090},  # -0.55% / TP +0.90%
    "step_2": {"discount": 0.0175, "alloc": 5.60, "tp": 0.0110},  # -1.75% / TP +1.10%
}


def send_telegram(text: str) -> None:
    """Sends high-priority trade alerts to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning(f"Telegram alert delivery error: {e}")


class StandaloneBybitBot:
    """Autonomous 2-Step Spot Micro-Grid Engine for Bybit Kazakhstan."""

    def __init__(self) -> None:
        self.client = BybitV5Client(BYBIT_API_KEY, BYBIT_API_SECRET, domain="api.bybit.kz")
        self.bybit_last_cycles: Optional[int] = None
        self.last_sync_ts = 0.0
        self.running = True
        self.stats = {
            "symbol": SYMBOL,
            "total_usd": 0.0,
            "available_usdt": 0.0,
            "locked_usdt": 0.0,
            "sui_free": 0.0,
            "completed_cycles": 0,
            "net_profit_usd": 0.0,
            "open_orders": [],
            "last_price": 0.0,
            "updated_at": "",
        }

    def get_market_price(self) -> float:
        """Fetches current spot ticker price for SYMBOL."""
        try:
            res = self.client._request("GET", "/v5/market/tickers", params={"category": "spot", "symbol": SYMBOL})
            if res.get("retCode") == 0:
                tickers = res.get("result", {}).get("list", [])
                if tickers:
                    return float(tickers[0].get("lastPrice") or 0.0)
        except Exception as e:
            logger.warning(f"Failed to fetch market ticker: {e}")
        return 0.0

    def step(self) -> None:
        """Single step of micro-grid trading cycle."""
        if not self.client.is_configured:
            logger.error("Bybit credentials not configured in environment!")
            return

        try:
            # 1. Sync Wallet Balance
            bal = self.client.get_wallet_balance("UNIFIED")
            if bal.get("retCode") != 0:
                logger.warning(f"Wallet sync error ({bal.get('retCode')}): {bal.get('retMsg')}")
                return

            avail_usdt = bal.get("available_usdt", 0.0)
            locked_usdt = bal.get("locked_usdt", 0.0)
            total_usd = bal.get("total_usd", 0.0)
            sui_coin = bal.get("coins", {}).get("SUI", {})
            sui_free = sui_coin.get("free", 0.0)

            # 2. Sync Open Orders
            open_orders = self.client.get_open_orders(SYMBOL)
            open_buys = [o for o in open_orders if o.get("side") == "Buy"]
            open_sells = [o for o in open_orders if o.get("side") == "Sell"]

            # 3. Market Price
            sui_price = self.get_market_price()
            if sui_price <= 0:
                return

            # Update live stats
            self.stats.update({
                "total_usd": round(total_usd, 4),
                "available_usdt": round(avail_usdt, 4),
                "locked_usdt": round(locked_usdt, 4),
                "sui_free": round(sui_free, 4),
                "open_orders": open_orders,
                "last_price": sui_price,
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            # 4. Sync Executions & Realized Profit
            now = time.time()
            if now - self.last_sync_ts > 30:
                self.last_sync_ts = now
                execs = self.client.get_execution_history(SYMBOL, limit=20)
                if execs:
                    tot_fees = sum(float(e.get("execFee") or 0.0) for e in execs)
                    sell_execs = [e for e in execs if e.get("side") == "Sell"]
                    cycles = len(sell_execs)

                    gross = 0.0
                    for s in sell_execs:
                        s_p = float(s.get("execPrice") or 0.0)
                        s_q = float(s.get("execQty") or 0.0)
                        gross += s_p * s_q * 0.0090

                    net = max(0.0, gross - tot_fees)
                    self.stats["completed_cycles"] = cycles
                    self.stats["net_profit_usd"] = round(net, 4)

                    if self.bybit_last_cycles is not None and cycles > self.bybit_last_cycles:
                        last_sell = sell_execs[0] if sell_execs else {}
                        s_p = last_sell.get("execPrice", "")
                        s_q = last_sell.get("execQty", "")
                        send_telegram(
                            f"🏆 **[BYBIT.KZ: ЦИКЛ ЗАКРЫТ В ПЛЮС!]**\n\n"
                            f"Пара: **{SYMBOL}**\n"
                            f"Продано: **{s_q} SUI** @ **${s_p}**\n"
                            f"Чистая прибыль: **+${net:.4f} USDT**\n"
                            f"Всего закрыто циклов: **{cycles}**\n"
                            f"Баланс аккаунта: **${total_usd:.2f} USDT**"
                        )
                    self.bybit_last_cycles = cycles

            # 5. Take-Profit Sell Logic (PostOnly Maker)
            current_pos_val = sui_free * sui_price
            if current_pos_val >= 5.00 and len(open_sells) < 2:
                tp_pct = 0.0090
                tp_price = round(sui_price * (1.0 + tp_pct), 4)
                sell_qty = math.floor(sui_free * 100) / 100.0

                if (sell_qty * tp_price) >= 5.00:
                    logger.info(f"🟢 [Bybit.kz] Выставляем ТЕЙК-ПРОФИТ: {sell_qty} SUI @ ${tp_price} (+{tp_pct*100:.2f}%)")
                    resp = self.client.create_limit_order(SYMBOL, "Sell", sell_qty, tp_price, post_only=True)
                    if resp.get("retCode") == 0:
                        send_telegram(
                            f"🟢 **[BYBIT.KZ: ТЕЙК-ПРОФИТ ВЫСТАВЛЕН]**\n\n"
                            f"Пара: **{SYMBOL}**\n"
                            f"Объем: **{sell_qty} SUI** (~${round(sell_qty * tp_price, 2)})\n"
                            f"Цена выхода: **${tp_price}** (+{tp_pct*100:.2f}%)\n"
                            f"Ордер ID: `{resp.get('result', {}).get('orderId')}`"
                        )

            # 6. Drift & TTL Management for resting BUY orders
            t1 = round(sui_price * (1.0 - GRID_CONFIG["step_1"]["discount"]), 4)
            t2 = round(sui_price * (1.0 - GRID_CONFIG["step_2"]["discount"]), 4)
            current_time = time.time()

            for b_ord in list(open_buys):
                ord_id = b_ord.get("orderId")
                ord_price = float(b_ord.get("price", 0.0))
                if not ord_id or ord_price <= 0:
                    continue

                created_time = float(b_ord.get("createdTime", current_time * 1000)) / 1000.0
                is_expired = (current_time - created_time) > 1200

                d1 = abs(t1 - ord_price) / ord_price
                d2 = abs(t2 - ord_price) / ord_price
                target_drift_pct = min(d1, d2)

                if target_drift_pct > 0.015 or is_expired:
                    logger.info(
                        f"🟡 [Bybit.kz] Ре-пеггинг ордера {ord_id} "
                        f"(Дрейф цели: {target_drift_pct*100:.2f}%, Возраст: {int(current_time - created_time)}с)"
                    )
                    resp_c = self.client.cancel_order(SYMBOL, ord_id)
                    if resp_c.get("retCode") == 0 and b_ord in open_buys:
                        open_buys.remove(b_ord)

            # 7. Grid Entry: Step 1 (-0.55%) and Step 2 (-1.75%)
            has_step1 = any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys)
            if not has_step1 and avail_usdt >= 5.10:
                alloc_1 = min(GRID_CONFIG["step_1"]["alloc"], avail_usdt)
                clip_1 = math.floor((alloc_1 / t1) * 100) / 100.0
                val_1 = clip_1 * t1
                if val_1 >= 5.00 and val_1 <= avail_usdt:
                    logger.info(f"🟡 [Bybit.kz][Ступень 1] Покупка: {clip_1} SUI @ ${t1} (-{GRID_CONFIG['step_1']['discount']*100:.2f}%)")
                    resp1 = self.client.create_limit_order(SYMBOL, "Buy", clip_1, t1, post_only=True)
                    if resp1.get("retCode") == 0:
                        avail_usdt -= val_1

            has_step2 = any(abs(float(o.get("price", 0)) - t2) / t2 < 0.010 for o in open_buys)
            if not has_step2 and avail_usdt >= 5.00:
                alloc_2 = min(GRID_CONFIG["step_2"]["alloc"], avail_usdt)
                clip_2 = math.floor((alloc_2 / t2) * 100) / 100.0
                val_2 = clip_2 * t2
                if val_2 >= 5.00 and val_2 <= avail_usdt:
                    logger.info(f"🟡 [Bybit.kz][Ступень 2] Покупка: {clip_2} SUI @ ${t2} (-{GRID_CONFIG['step_2']['discount']*100:.2f}%)")
                    resp2 = self.client.create_limit_order(SYMBOL, "Buy", clip_2, t2, post_only=True)
                    if resp2.get("retCode") == 0:
                        avail_usdt -= val_2

        except Exception as e:
            logger.error(f"Trading loop exception: {e}")

    def run_forever(self) -> None:
        """Main execution loop (runs every 10 seconds)."""
        logger.info("🚀 [Bybit Kazakhstan Standalone Bot] Запущен в автономном режиме!")
        logger.info(f"Пара: {SYMBOL} | Модель: 2-Step Micro-Grid | Эндпоинт: api.bybit.kz")

        while self.running:
            self.step()
            time.sleep(10)


class SimpleDashboardHandler(http.server.BaseHTTPRequestHandler):
    """Ultra-lightweight embedded web server for mobile browser monitoring."""
    bot_instance: Optional[StandaloneBybitBot] = None

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = self.bot_instance.stats if self.bot_instance else {}
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        st = self.bot_instance.stats if self.bot_instance else {}
        orders_html = "".join([
            f"<tr><td class='{o.get('side', '').lower()}'>{o.get('side')}</td>"
            f"<td>${float(o.get('price', 0)):.4f}</td>"
            f"<td>{float(o.get('qty', 0)):.2f}</td>"
            f"<td>${float(o.get('qty', 0))*float(o.get('price', 0)):.2f}</td></tr>"
            for o in st.get('open_orders', [])
        ])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bybit KZ Bot Dashboard</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: -apple-system, system-ui, sans-serif; padding: 15px; margin: 0; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 16px; margin-bottom: 12px; border: 1px solid #334155; }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.2rem; }}
        .metric {{ font-size: 1.8rem; font-weight: bold; color: #10b981; }}
        .label {{ font-size: 0.85rem; color: #94a3b8; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.85rem; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #334155; }}
        th {{ color: #94a3b8; }}
        .buy {{ color: #38bdf8; font-weight: bold; }}
        .sell {{ color: #f59e0b; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ Bybit Kazakhstan Bot</h2>
        <div class="label">Пара: {st.get('symbol')} | Спот: ${st.get('last_price')}</div>
        <div class="metric">${st.get('total_usd', 0.0):.2f} USDT</div>
        <div class="label">Свободно: ${st.get('available_usdt', 0.0):.2f} | В ордерах: ${st.get('locked_usdt', 0.0):.2f}</div>
        <div class="label" style="margin-top: 6px; color: #10b981;">Закрыто циклов: {st.get('completed_cycles', 0)} | Профит: +${st.get('net_profit_usd', 0.0):.4f} USDT</div>
    </div>

    <div class="card">
        <h2>📖 Активные ордера в стакане</h2>
        <table>
            <tr><th>Сторона</th><th>Цена</th><th>Объем</th><th>Сумма</th></tr>
            {orders_html}
        </table>
        <div class="label" style="margin-top: 8px;">Обновлено: {st.get('updated_at')}</div>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        pass


def start_server(bot: StandaloneBybitBot) -> None:
    """Runs local mobile dashboard on background thread."""
    SimpleDashboardHandler.bot_instance = bot
    try:
        with socketserver.TCPServer(("", PORT), SimpleDashboardHandler) as httpd:
            logger.info(f"📱 Мобильный дашборд: http://localhost:{PORT}/")
            httpd.serve_forever()
    except Exception as e:
        logger.warning(f"Dashboard server bind warning: {e}")


if __name__ == "__main__":
    bot = StandaloneBybitBot()
    t_web = threading.Thread(target=start_server, args=(bot,), daemon=True)
    t_web.start()
    bot.run_forever()
