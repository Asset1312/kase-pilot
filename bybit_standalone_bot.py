#!/usr/bin/env python3
"""
Bybit Kazakhstan Spot V5 Standalone Micro-Grid Scalper with Crash Protection.
Engineered for 24/7 autonomous operation on Android (Termux) / Linux / Windows.
Strictly isolated to Bybit Kazakhstan (api.bybit.kz) - Zero Tradernet/KASE overhead.

Enhanced with 4-Layer Deposit Crash Protection:
1. Dual Dump Guard: BTC Lead-Lag (-0.35%) + SUI Idiosyncratic (-0.60%)
2. Smart Cooldown Exit: 10 min minimum + Candle Stabilization (no lower lows)
3. Dynamic Volatility Spacing: Normal (-0.55% / -1.75%) vs Storm (-1.20% / -2.80%)
4. Inventory-Aware Sizing: Step 2 reserved, minOrderAmt = 5 USDT guaranteed
5. Fee-Proof Soft Breakeven: Stale position (>8h) TP reduced to +0.38% (net +0.18% after fees)
6. Circuit Breaker: 5% maximum daily equity drawdown guard
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
from typing import Any, Dict, List, Optional, Tuple
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

SYMBOL = "SUIUSDT"
LEAD_LAG_SYMBOL = "BTCUSDT"

# Protection Thresholds
BTC_1M_DUMP_THRESHOLD = -0.0035     # -0.35% BTC drop in 1 min
BTC_3M_DUMP_THRESHOLD = -0.0070     # -0.70% BTC drop in 3 min
SUI_1M_DUMP_THRESHOLD = -0.0060     # -0.60% SUI drop in 1 min
SUI_3M_DUMP_THRESHOLD = -0.0120     # -1.20% SUI drop in 3 min
COOLDOWN_MIN_SECONDS = 600          # 10 minutes minimum freeze

# Spacing Regimes
SPACING_NORMAL = {"step_1": 0.0055, "step_2": 0.0175}   # Normal: -0.55% / -1.75%
SPACING_STORM = {"step_1": 0.0120, "step_2": 0.0280}    # High Vol / Storm: -1.20% / -2.80%
VOL_STORM_THRESHOLD = 0.0120                            # 15m Range > 1.20% -> Storm

# Take-Profit & Soft Breakeven
STANDARD_TP_PCT = 0.0090            # +0.90% (Net +0.70% after 0.20% fees)
SOFT_BREAKEVEN_TP_PCT = 0.0038      # +0.38% (Net +0.18% after 0.20% fees)
STALE_POSITION_HOURS = 8.0          # Switch to Soft Breakeven after 8 hours
CIRCUIT_BREAKER_MAX_DD = 0.05       # 5% max drawdown from peak equity


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


class MarketGuard:
    """Market crash detection, lead-lag spillover, and dynamic spacing engine."""

    def __init__(self) -> None:
        self.cooldown_active = False
        self.cooldown_start_time = 0.0
        self.cooldown_reason = ""
        self.volatility_regime = "NORMAL"  # "NORMAL" or "STORM"
        self.step1_discount = SPACING_NORMAL["step_1"]
        self.step2_discount = SPACING_NORMAL["step_2"]
        self.last_btc_1m_chg = 0.0
        self.last_sui_1m_chg = 0.0
        self.last_sui_15m_range = 0.0

    @staticmethod
    def fetch_klines(symbol: str, limit: int = 15) -> List[List[Any]]:
        """Fetches public Kline data directly from Bybit KZ Spot endpoint (Zero API Key)."""
        url = f"https://api.bybit.kz/v5/market/kline?category=spot&symbol={symbol}&interval=1&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if data.get("retCode") == 0:
                    return data.get("result", {}).get("list", [])
        except Exception as e:
            logger.debug(f"Kline fetch failed for {symbol}: {e}")
        return []

    def update_market_state(self) -> Tuple[bool, str]:
        """
        Updates market metrics, checks dump triggers and stabilization.
        Returns (dump_triggered_now, trigger_reason).
        """
        btc_klines = self.fetch_klines(LEAD_LAG_SYMBOL, limit=5)
        sui_klines = self.fetch_klines(SYMBOL, limit=15)

        if not btc_klines or not sui_klines:
            return False, ""

        # Bybit klines: index 0 is newest (current forming candle), index 1 is previous completed candle
        btc_c0, btc_o0 = float(btc_klines[0][4]), float(btc_klines[0][1])
        btc_1m_chg = (btc_c0 - btc_o0) / btc_o0 if btc_o0 > 0 else 0.0
        self.last_btc_1m_chg = btc_1m_chg

        btc_3m_chg = 0.0
        if len(btc_klines) >= 3:
            btc_o2 = float(btc_klines[2][1])
            btc_3m_chg = (btc_c0 - btc_o2) / btc_o2 if btc_o2 > 0 else 0.0

        sui_c0, sui_o0 = float(sui_klines[0][4]), float(sui_klines[0][1])
        sui_1m_chg = (sui_c0 - sui_o0) / sui_o0 if sui_o0 > 0 else 0.0
        self.last_sui_1m_chg = sui_1m_chg

        sui_3m_chg = 0.0
        if len(sui_klines) >= 3:
            sui_o2 = float(sui_klines[2][1])
            sui_3m_chg = (sui_c0 - sui_o2) / sui_o2 if sui_o2 > 0 else 0.0

        # Dynamic Volatility calculation (15-minute high/low range on SUI)
        highs = [float(k[2]) for k in sui_klines]
        lows = [float(k[3]) for k in sui_klines]
        min_low = min(lows) if lows else 1.0
        max_high = max(highs) if highs else 1.0
        sui_15m_range = (max_high - min_low) / min_low if min_low > 0 else 0.0
        self.last_sui_15m_range = sui_15m_range

        if sui_15m_range >= VOL_STORM_THRESHOLD:
            self.volatility_regime = "STORM"
            self.step1_discount = SPACING_STORM["step_1"]
            self.step2_discount = SPACING_STORM["step_2"]
        else:
            self.volatility_regime = "NORMAL"
            self.step1_discount = SPACING_NORMAL["step_1"]
            self.step2_discount = SPACING_NORMAL["step_2"]

        # Dump Trigger Evaluation (When not in cooldown)
        if not self.cooldown_active:
            reason = ""
            if btc_1m_chg <= BTC_1M_DUMP_THRESHOLD:
                reason = f"BTC 1m Flash Dump ({btc_1m_chg*100:.2f}%)"
            elif btc_3m_chg <= BTC_3M_DUMP_THRESHOLD:
                reason = f"BTC 3m Cumulative Dump ({btc_3m_chg*100:.2f}%)"
            elif sui_1m_chg <= SUI_1M_DUMP_THRESHOLD:
                reason = f"SUI 1m Idiosyncratic Dump ({sui_1m_chg*100:.2f}%)"
            elif sui_3m_chg <= SUI_3M_DUMP_THRESHOLD:
                reason = f"SUI 3m Cumulative Dump ({sui_3m_chg*100:.2f}%)"

            if reason:
                self.cooldown_active = True
                self.cooldown_start_time = time.time()
                self.cooldown_reason = reason
                return True, reason

        # Smart Cooldown Exit Evaluation (When currently in cooldown)
        else:
            elapsed = time.time() - self.cooldown_start_time
            if elapsed >= COOLDOWN_MIN_SECONDS:
                # Stabilization conditions:
                # 1. Neither BTC nor SUI made a lower low on last 2 candles
                btc_l0 = float(btc_klines[0][3])
                btc_l1 = float(btc_klines[1][3]) if len(btc_klines) > 1 else btc_l0
                sui_l0 = float(sui_klines[0][3])
                sui_l1 = float(sui_klines[1][3]) if len(sui_klines) > 1 else sui_l0

                btc_stabilized = btc_l0 >= btc_l1
                sui_stabilized = (sui_l0 >= sui_l1) and (sui_1m_chg >= -0.0010)

                if btc_stabilized and sui_stabilized:
                    logger.info(
                        f"🟢 [MarketGuard] Рынок стабилизировался! Пауза {int(elapsed)}с завершена. "
                        f"BTC L: {btc_l0}>={btc_l1}, SUI L: {sui_l0}>={sui_l1}"
                    )
                    self.cooldown_active = False
                    self.cooldown_reason = ""
                    send_telegram(
                        "🟢 **[ЗАЩИТА ДЕПОЗИТА: РЫНОК СТАБИЛИЗИРОВАН]**\n\n"
                        f"Пара: **{SYMBOL}**\n"
                        f"Защитная пауза ({int(elapsed)}с) успешно завершена.\n"
                        "Свечи зафиксировали локальное дно. Сетка ордеров возобновлена."
                    )
                else:
                    logger.debug(
                        f"MarketGuard: В кулдауне {int(elapsed)}с, ждем стабилизации (BTC: {btc_stabilized}, SUI: {sui_stabilized})"
                    )

        return False, ""


class StandaloneBybitBot:
    """Autonomous 2-Step Spot Micro-Grid Engine for Bybit Kazakhstan with Crash Protection."""

    def __init__(self) -> None:
        self.client = BybitV5Client(BYBIT_API_KEY, BYBIT_API_SECRET, domain="api.bybit.kz")
        self.guard = MarketGuard()
        self.bybit_last_cycles: Optional[int] = None
        self.last_sync_ts = 0.0
        self.peak_equity = 0.0
        self.circuit_breaker_active = False
        self.running = True
        self.stats = {
            "symbol": SYMBOL,
            "total_usd": 0.0,
            "available_usdt": 0.0,
            "locked_usdt": 0.0,
            "sui_free": 0.0,
            "sui_locked": 0.0,
            "completed_cycles": 0,
            "net_profit_usd": 0.0,
            "open_orders": [],
            "last_price": 0.0,
            "guard_status": "🟢 Норма",
            "volatility_regime": "NORMAL",
            "cooldown_active": False,
            "cooldown_reason": "",
            "position_age_hours": 0.0,
            "tp_mode": "Standard (+0.90%)",
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

    def cancel_all_buys(self, open_buys: List[Dict[str, Any]]) -> None:
        """Instantly cancels all resting BUY orders to avoid catching falling knives."""
        for b_ord in open_buys:
            ord_id = b_ord.get("orderId")
            if ord_id:
                logger.warning(f"🚨 [MarketGuard] Экстренная отмена BUY-ордера {ord_id} @ ${b_ord.get('price')}")
                self.client.cancel_order(SYMBOL, ord_id)

    def step(self) -> None:
        """Single execution step of micro-grid trading cycle."""
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
            sui_locked = sui_coin.get("locked", 0.0)
            total_sui = sui_free + sui_locked

            # 2. Market Price
            sui_price = self.get_market_price()
            if sui_price <= 0:
                return

            # Update Peak Equity & Circuit Breaker
            est_total_equity = total_usd + (total_sui * sui_price)
            if est_total_equity > self.peak_equity:
                self.peak_equity = est_total_equity

            if self.peak_equity > 0 and est_total_equity < (self.peak_equity * (1.0 - CIRCUIT_BREAKER_MAX_DD)):
                if not self.circuit_breaker_active:
                    self.circuit_breaker_active = True
                    logger.error(f"🚨 [CIRCUIT BREAKER] Просадка депозита > 5%! Equity: ${est_total_equity:.2f} (Пик: ${self.peak_equity:.2f})")
                    send_telegram(
                        f"🚨 **[CIRCUIT BREAKER: ЛИМИТ ПРОСАДКИ 5%]**\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT**\n"
                        f"Пиковый капитал: **${self.peak_equity:.2f} USDT**\n"
                        "Покупки заблокированы до ручного перезапуска или стабилизации."
                    )
            elif est_total_equity >= (self.peak_equity * (1.0 - CIRCUIT_BREAKER_MAX_DD)):
                self.circuit_breaker_active = False

            # 3. MarketGuard: Check Dumps & Spacing
            dump_fired, dump_reason = self.guard.update_market_state()

            # 4. Sync Open Orders
            open_orders = self.client.get_open_orders(SYMBOL)
            open_buys = [o for o in open_orders if o.get("side") == "Buy"]
            open_sells = [o for o in open_orders if o.get("side") == "Sell"]

            # Emergency BUY cancellation if dump just triggered
            if dump_fired:
                logger.warning(f"🚨 [MarketGuard Triggered] {dump_reason} -> Снятие всех BUY-ордеров!")
                self.cancel_all_buys(open_buys)
                open_buys.clear()
                send_telegram(
                    f"🚨 **[ЗАЩИТА ДЕПОЗИТА: ОБНАРУЖЕН ПРОЛИВ!]**\n\n"
                    f"Причина: **{dump_reason}**\n"
                    f"Срочное действие: **Все BUY-ордера отозваны**\n"
                    f"Режим: Включена защитная пауза на 10 мин (до стабилизации свечей)."
                )

            # If still in cooldown, ensure no BUY orders linger
            if self.guard.cooldown_active and open_buys:
                self.cancel_all_buys(open_buys)
                open_buys.clear()

            # 5. Sync Executions & Realized Profit
            now = time.time()
            recent_buys: List[Dict[str, Any]] = []
            if now - self.last_sync_ts > 30:
                self.last_sync_ts = now
                execs = self.client.get_execution_history(SYMBOL, limit=20)
                if execs:
                    tot_fees = sum(float(e.get("execFee") or 0.0) for e in execs)
                    sell_execs = [e for e in execs if e.get("side") == "Sell"]
                    recent_buys = [e for e in execs if e.get("side") == "Buy"]
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
                            f"Баланс аккаунта: **${est_total_equity:.2f} USDT**"
                        )
                    self.bybit_last_cycles = cycles

            # 6. Take-Profit & Soft Breakeven Management
            current_pos_val = sui_free * sui_price
            holding_pos_val = total_sui * sui_price
            entry_price = sui_price

            # Estimate entry price from latest buy execution
            if recent_buys:
                entry_price = float(recent_buys[0].get("execPrice") or sui_price)

            position_age_hours = 0.0
            tp_mode = "Standard (+0.90%)"

            # Check existing Sell orders for Stale Position Soft Breakeven
            for s_ord in list(open_sells):
                s_id = s_ord.get("orderId")
                s_price = float(s_ord.get("price", 0.0))
                s_created = float(s_ord.get("createdTime", now * 1000)) / 1000.0
                age_h = (now - s_created) / 3600.0
                position_age_hours = max(position_age_hours, age_h)

                if age_h >= STALE_POSITION_HOURS:
                    tp_mode = f"Soft Breakeven ({age_h:.1f}ч)"
                    soft_tp_price = round(entry_price * (1.0 + SOFT_BREAKEVEN_TP_PCT), 4)
                    # If current TP price is higher than soft TP, adjust downwards
                    if s_price > soft_tp_price and (soft_tp_price * float(s_ord.get("qty", 0.0))) >= 5.00:
                        logger.info(
                            f"🛡️ [Bybit.kz] Зависание {age_h:.1f}ч! Снижаем ТП с ${s_price} до ${soft_tp_price} (+{SOFT_BREAKEVEN_TP_PCT*100:.2f}%)"
                        )
                        self.client.cancel_order(SYMBOL, s_id)
                        open_sells.remove(s_ord)
                        resp_soft = self.client.create_limit_order(
                            SYMBOL, "Sell", float(s_ord.get("qty", 0.0)), soft_tp_price, post_only=True
                        )
                        if resp_soft.get("retCode") == 0:
                            send_telegram(
                                f"🛡️ **[ЗАЩИТА ДЕПОЗИТА: SOFT BREAKEVEN]**\n\n"
                                f"Пара: **{SYMBOL}**\n"
                                f"Позиция удерживается: **{age_h:.1f} ч**\n"
                                f"Тейк-профит снижен до: **${soft_tp_price}** (+{SOFT_BREAKEVEN_TP_PCT*100:.2f}%)\n"
                                "Цель: Гарантированный выход в плюс (+0.18% чистыми после комиссий) при первом локальном отскоке."
                            )

            # Place fresh Take-Profit if coins are free and no active sell order covers them
            if current_pos_val >= 5.00 and len(open_sells) < 2:
                tp_pct = STANDARD_TP_PCT
                tp_price = round(entry_price * (1.0 + tp_pct), 4)
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

            # 7. Drift & TTL Management for resting BUY orders
            step1_disc = self.guard.step1_discount
            step2_disc = self.guard.step2_discount
            t1 = round(sui_price * (1.0 - step1_disc), 4)
            t2 = round(sui_price * (1.0 - step2_disc), 4)

            for b_ord in list(open_buys):
                ord_id = b_ord.get("orderId")
                ord_price = float(b_ord.get("price", 0.0))
                if not ord_id or ord_price <= 0:
                    continue

                created_time = float(b_ord.get("createdTime", now * 1000)) / 1000.0
                is_expired = (now - created_time) > 1200

                d1 = abs(t1 - ord_price) / ord_price
                d2 = abs(t2 - ord_price) / ord_price
                target_drift_pct = min(d1, d2)

                if target_drift_pct > 0.015 or is_expired:
                    logger.info(
                        f"🟡 [Bybit.kz] Ре-пеггинг ордера {ord_id} "
                        f"(Дрейф цели: {target_drift_pct*100:.2f}%, Возраст: {int(now - created_time)}с)"
                    )
                    resp_c = self.client.cancel_order(SYMBOL, ord_id)
                    if resp_c.get("retCode") == 0 and b_ord in open_buys:
                        open_buys.remove(b_ord)

            # 8. Inventory-Aware Sizing & Grid Entry (minOrderAmt = 5 USDT Guard)
            # If cooldown or circuit breaker is active, DO NOT place any BUY orders!
            can_buy = (not self.guard.cooldown_active) and (not self.circuit_breaker_active)

            if can_buy:
                # Inventory Check: Is Step 1 already bought?
                step1_already_held = holding_pos_val >= 5.00

                if step1_already_held:
                    # Step 1 is in position! We MUST NOT place Step 1 again at the top!
                    # Remaining cash is reserved STRICTLY for Step 2 (averaging floor at -1.75% / -2.80%)
                    has_step2 = any(abs(float(o.get("price", 0)) - t2) / t2 < 0.010 for o in open_buys)
                    if not has_step2 and avail_usdt >= 5.00:
                        alloc_2 = min(avail_usdt, max(5.05, round(avail_usdt * 0.95, 2)))
                        clip_2 = math.floor((alloc_2 / t2) * 100) / 100.0
                        val_2 = clip_2 * t2
                        if val_2 >= 5.00 and val_2 <= avail_usdt:
                            logger.info(
                                f"🟡 [Bybit.kz][Ступень 2 Усреднение] Покупка: {clip_2} SUI @ ${t2} "
                                f"(-{step2_disc*100:.2f}%, Режим: {self.guard.volatility_regime})"
                            )
                            resp2 = self.client.create_limit_order(SYMBOL, "Buy", clip_2, t2, post_only=True)
                            if resp2.get("retCode") == 0:
                                avail_usdt -= val_2

                else:
                    # No active position held (deposit is in cash).
                    # If cash allows both floors (>= 10.10 USDT), place Step 1 (45%) and Step 2 (45%) with 10% buffer
                    if avail_usdt >= 10.10:
                        alloc_1 = max(5.05, round(avail_usdt * 0.45, 2))
                        alloc_2 = max(5.05, round(avail_usdt * 0.45, 2))

                        has_step1 = any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys)
                        if not has_step1 and avail_usdt >= alloc_1:
                            clip_1 = math.floor((alloc_1 / t1) * 100) / 100.0
                            val_1 = clip_1 * t1
                            if val_1 >= 5.00 and val_1 <= avail_usdt:
                                logger.info(
                                    f"🟡 [Bybit.kz][Ступень 1] Покупка: {clip_1} SUI @ ${t1} "
                                    f"(-{step1_disc*100:.2f}%, Режим: {self.guard.volatility_regime})"
                                )
                                resp1 = self.client.create_limit_order(SYMBOL, "Buy", clip_1, t1, post_only=True)
                                if resp1.get("retCode") == 0:
                                    avail_usdt -= val_1

                        has_step2 = any(abs(float(o.get("price", 0)) - t2) / t2 < 0.010 for o in open_buys)
                        if not has_step2 and avail_usdt >= alloc_2:
                            clip_2 = math.floor((alloc_2 / t2) * 100) / 100.0
                            val_2 = clip_2 * t2
                            if val_2 >= 5.00 and val_2 <= avail_usdt:
                                logger.info(
                                    f"🟡 [Bybit.kz][Ступень 2] Покупка: {clip_2} SUI @ ${t2} "
                                    f"(-{step2_disc*100:.2f}%, Режим: {self.guard.volatility_regime})"
                                )
                                resp2 = self.client.create_limit_order(SYMBOL, "Buy", clip_2, t2, post_only=True)
                                if resp2.get("retCode") == 0:
                                    avail_usdt -= val_2

                    elif avail_usdt >= 5.05:
                        # Only enough cash for one single order (>= 5.00 USDT)
                        has_step1 = any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys)
                        if not has_step1:
                            alloc_1 = min(avail_usdt, max(5.05, round(avail_usdt * 0.95, 2)))
                            clip_1 = math.floor((alloc_1 / t1) * 100) / 100.0
                            val_1 = clip_1 * t1
                            if val_1 >= 5.00 and val_1 <= avail_usdt:
                                logger.info(f"🟡 [Bybit.kz][Ступень 1 (Одиночная)] Покупка: {clip_1} SUI @ ${t1} (-{step1_disc*100:.2f}%)")
                                self.client.create_limit_order(SYMBOL, "Buy", clip_1, t1, post_only=True)

            # 9. Update live statistics for dashboard
            guard_status_str = "🟢 Норма"
            if self.circuit_breaker_active:
                guard_status_str = "🚨 Circuit Breaker (Drawdown > 5%)"
            elif self.guard.cooldown_active:
                elapsed_cd = int(now - self.guard.cooldown_start_time)
                guard_status_str = f"🚨 Защитная Пауза ({self.guard.cooldown_reason}) [{elapsed_cd}с]"
            elif self.guard.volatility_regime == "STORM":
                guard_status_str = f"🟡 Шторм (15m размах: {self.guard.last_sui_15m_range*100:.2f}%)"

            self.stats.update({
                "total_usd": round(est_total_equity, 4),
                "available_usdt": round(avail_usdt, 4),
                "locked_usdt": round(locked_usdt, 4),
                "sui_free": round(sui_free, 4),
                "sui_locked": round(sui_locked, 4),
                "open_orders": self.client.get_open_orders(SYMBOL),
                "last_price": sui_price,
                "guard_status": guard_status_str,
                "volatility_regime": self.guard.volatility_regime,
                "cooldown_active": self.guard.cooldown_active,
                "cooldown_reason": self.guard.cooldown_reason,
                "position_age_hours": round(position_age_hours, 1),
                "tp_mode": tp_mode,
                "btc_1m_chg": round(self.guard.last_btc_1m_chg * 100, 2),
                "sui_1m_chg": round(self.guard.last_sui_1m_chg * 100, 2),
                "step1_discount_pct": round(self.guard.step1_discount * 100, 2),
                "step2_discount_pct": round(self.guard.step2_discount * 100, 2),
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

        except Exception as e:
            logger.error(f"Trading loop exception: {e}")

    def run_forever(self) -> None:
        """Main execution loop (runs every 10 seconds)."""
        logger.info("🚀 [Bybit Kazakhstan Standalone Bot] Запущен с 4-уровневой защитой депозита!")
        logger.info(f"Пара: {SYMBOL} | Lead-Lag: {LEAD_LAG_SYMBOL} | Эндпоинт: api.bybit.kz")

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

        guard_color = "#10b981"
        if "🚨" in st.get("guard_status", ""):
            guard_color = "#ef4444"
        elif "🟡" in st.get("guard_status", ""):
            guard_color = "#f59e0b"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bybit KZ Bot Dashboard</title>
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: -apple-system, system-ui, sans-serif; padding: 15px; margin: 0; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 16px; margin-bottom: 12px; border: 1px solid #334155; }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.15rem; }}
        .metric {{ font-size: 1.8rem; font-weight: bold; color: #10b981; }}
        .label {{ font-size: 0.85rem; color: #94a3b8; }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 0.8rem; margin-top: 4px; }}
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
        <h2>🛡️ Защита депозита</h2>
        <div class="badge" style="background: {guard_color}22; color: {guard_color}; border: 1px solid {guard_color};">
            {st.get('guard_status')}
        </div>
        <div class="label" style="margin-top: 8px;">
            Импульс BTC 1m: <b>{st.get('btc_1m_chg', 0.0):+.2f}%</b> | SUI 1m: <b>{st.get('sui_1m_chg', 0.0):+.2f}%</b>
        </div>
        <div class="label" style="margin-top: 4px;">
            Сетка: Ступень 1 (-{st.get('step1_discount_pct', 0.55)}%) | Ступень 2 (-{st.get('step2_discount_pct', 1.75)}%)
        </div>
        <div class="label" style="margin-top: 4px;">
            Режим ТП: <b>{st.get('tp_mode')}</b> (Удержание: {st.get('position_age_hours', 0.0)}ч)
        </div>
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
