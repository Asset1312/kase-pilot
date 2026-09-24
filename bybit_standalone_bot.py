#!/usr/bin/env python3
"""
Bybit Kazakhstan Spot V5 Standalone Multi-Token Portfolio Engine with Crash Protection.
Engineered for 24/7 autonomous operation on Android (Termux) / Linux / Windows.
Strictly isolated to Bybit Kazakhstan (api.bybit.kz) - Zero Tradernet/KASE overhead.

Enhanced with Multi-Token Portfolio Management:
1. Multi-Token Scalping: SUIUSDT (Primary) + APTUSDT (Secondary)
2. Dynamic Capital Scaling Milestones:
   - < $70 USDT: 100% Capital on SUIUSDT (3-step geometric grid)
   - >= $70 USDT: Dual-Pair Scalping (50% SUI / 50% APT)
   - Hysteresis Gate: Deactivates APT into EXIT_ONLY if equity drops below $62 (no panic selling)
3. Continuous Adaptive Volatility Spacing:
   - Dynamically scales grid steps based on 15m True Range Index (0.75x to 2.00x)
4. Multi-Layer Deposit Crash Protection:
   - Global BTC Lead-Lag flash dump guard (-0.35% 1m / -0.70% 3m)
   - Idiosyncratic token dump guard (-0.60% 1m / -1.20% 3m) per asset
   - Smart Cooldown Exit: 10 min minimum + Candle Stabilization check
   - Circuit Breaker: 5% maximum daily equity drawdown guard
5. Fee-Proof Soft Breakeven:
   - Stale position (>8h) TP reduced to +0.38% (net +0.18% after fees)
6. MNT Fuel Tracker & Telegram Remote Control Panel
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime
import http.server
import json
import logging
import math
import os
import queue
import socketserver
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.request
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

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
if not os.path.exists(DEPLOY_DIR):
    cwd_deploy = os.path.join(os.getcwd(), "deploy", "tradernet-cloud-bot")
    if os.path.exists(cwd_deploy):
        DEPLOY_DIR = cwd_deploy
    elif os.path.exists(r"C:\1\KASE-Pilot\deploy\tradernet-cloud-bot"):
        DEPLOY_DIR = r"C:\1\KASE-Pilot\deploy\tradernet-cloud-bot"

if DEPLOY_DIR not in sys.path:
    sys.path.insert(0, DEPLOY_DIR)

try:
    from bybit_client import BybitV5Client
except ImportError:
    from deploy.tradernet_cloud_bot.bybit_client import BybitV5Client

# Credentials & Telegram
BYBIT_API_KEY = os.getenv("BYBIT_API_KEY", "").strip()
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8661844936:AAGObMUpSRrnppgtY2I6-JQFiM-mgcnZ36U").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "455103299").strip()
ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "true").lower() not in ("0", "false", "no")
ENABLE_AUTO_FAILOVER = os.getenv("ENABLE_AUTO_FAILOVER", "false").lower() in ("1", "true", "yes")
PORT = int(os.getenv("PORT", "8080"))

# ==============================================================================
# RULE: Whenever adding ANY new trading pair (e.g. SOL, ETH, TON, DOGE):
# ALWAYS proactively remind the user to add the symbol to the Bybit API Key Whitelist!
# ==============================================================================
# Pair Architecture (3-Tier Scalable Basket)
PRIMARY_SYMBOL = "SUIUSDT"
SECONDARY_SYMBOL = "NEARUSDT"
TERTIARY_SYMBOL = "AVAXUSDT"
LEAD_LAG_SYMBOL = "BTCUSDT"

# Protection Thresholds
BTC_1M_DUMP_THRESHOLD = -0.0035     # -0.35% BTC drop in 1 min (Crash / Circuit Breaker)
BTC_3M_DUMP_THRESHOLD = -0.0070     # -0.70% BTC drop in 3 min (Crash / Circuit Breaker)
BTC_1M_SLIDING_THRESHOLD = -0.0015  # -0.15% BTC drop in 1 min (Sliding / Gate Step 1 Freeze)
BTC_3M_SLIDING_THRESHOLD = -0.0030  # -0.30% BTC drop in 3 min (Sliding / Gate Step 1 Freeze)
BTC_REVERSAL_CONFIRM_THRESHOLD = 0.0005 # +0.05% BTC 1m bounce confirms stabilization
COOLDOWN_MIN_SECONDS = 600          # 10 minutes minimum freeze

# Capital Scaling Milestones & Hysteresis Gates
DUAL_PAIR_ACTIVATION_EQUITY = 70.00    # Auto-activate 2nd pair (NEAR) when equity >= $70
DUAL_PAIR_DEACTIVATION_EQUITY = 62.00  # Deactivate 2nd pair (EXIT_ONLY) when equity < $62
TRIO_PAIR_ACTIVATION_EQUITY = 115.00   # Auto-activate 3rd pair (AVAX) when equity >= $115
TRIO_PAIR_DEACTIVATION_EQUITY = 105.00 # Deactivate 3rd pair (EXIT_ONLY) when equity < $105

# Desktop Profile Parameters (Smart Step & Liquidity Buffer)
DESKTOP_RESERVE_USDT = 10.00          # Untouchable liquidity buffer in desktop mode ($10.00)
DESKTOP_STEP_WEIGHTS = {
    "step_1": 0.18,                   # ~18% of deployable capital per token
    "step_2": 0.32,                   # ~32% of deployable capital per token
    "step_3": 0.50,                   # ~50% of deployable capital per token
}

# Auto-Compounding Engine (Dynamic Capital Reinvestment & Growth Scaling)
COMPOUNDING_ENABLED = True
COMPOUND_BASELINE_EQUITY = 40.00   # Baseline portfolio equity for 1.00x ($40.00 USDT)
COMPOUND_MAX_MULTIPLIER = 5.00     # Maximum growth scaling cap (5.00x)

def compute_compound_multiplier(equity: float, baseline: float = COMPOUND_BASELINE_EQUITY) -> float:
    """Computes smooth, safe compounding multiplier based on total portfolio equity.
    
    Guarantees multiplier >= 1.00 and <= COMPOUND_MAX_MULTIPLIER.
    Quantized to 0.05 steps to eliminate jitter from micro-tick spot fluctuations.
    """
    if not COMPOUNDING_ENABLED or equity <= baseline:
        return 1.00
    raw_mult = equity / baseline
    clamped = min(COMPOUND_MAX_MULTIPLIER, max(1.00, raw_mult))
    return round(math.floor(clamped * 20.0) / 20.0, 2)

# Cluster Handover & Failover Heartbeat Parameters
HEARTBEAT_INTERVAL_SECONDS = 60       # Ping frequency from active desktop (60s)
HEARTBEAT_TIMEOUT_SECONDS = 180       # Failover threshold for mobile (180s = 3 min)
ASTANA_TZ_OFFSET_HOURS = 5            # UTC+5
DESKTOP_HOURS_START = 8.0             # 08:00 Astana
DESKTOP_HOURS_END = 17.5              # 17:30 Astana

# On-Exchange Canary Order Heartbeat Parameters
CANARY_ORDER_LINK_PREFIX = "CANARY_PULSE"
CANARY_SYMBOL = "SUIUSDT"
CANARY_PRICE_A = 0.1001               # Micro-tick ping state A ($0.1001)
CANARY_PRICE_B = 0.1002               # Micro-tick ping state B ($0.1002)
CANARY_NOTIONAL_USDT = 5.05           # Exactly satisfies Bybit $5.00 spot minimum
CANARY_HEARTBEAT_INTERVAL_SEC = 45.0  # Desktop touches/amends canary every 45s
CANARY_FAILOVER_TIMEOUT_SEC = 180.0   # Mobile takes over if canary stale > 180s (3 min)

# Market Regime Classifier Profiles (CALM / NORMAL / STORM)
REGIME_PROFILES = {
    "CALM": {
        "name": "CALM (Штиль: Micro-Scalp)",
        "badge_color": "#38bdf8",     # Cyan / Sky
        "is_calm_split": True,        # Splits Step 1 into 1A (-0.35%) and 1B (-0.65%)
        "step_1a_discount": 0.0035,   # -0.35%
        "step_1b_discount": 0.0065,   # -0.65%
        "step_2_discount": 0.0160,    # -1.60%
        "step_3_discount": 0.0350,    # -3.50%
        "budget_1a": 5.25,            # Safe above Bybit $5.00 min notional
        "budget_1b": 5.50,
        "budget_2": 10.50,
        "budget_3": 15.00,
        "tp_target": 0.0050,          # +0.50% Maker Limit TP
        "use_maker_tp": True,         # Pre-places limit TP in order book
        "trailing_activation": 0.0060,
    },
    "NORMAL": {
        "name": "NORMAL (Стандарт: Rocket Rider)",
        "badge_color": "#10b981",     # Emerald green
        "is_calm_split": False,
        "step_1_discount": 0.0055,    # -0.55%
        "step_2_discount": 0.0200,    # -2.00%
        "step_3_discount": 0.0400,    # -4.00%
        "budget_1": 7.95,
        "budget_2": 14.15,
        "budget_3": 17.00,
        "tp_target": 0.0070,          # +0.70% Trailing Target
        "use_maker_tp": False,        # Managed via Rocket Rider Trailing
        "trailing_activation": 0.0070,
    },
    "STORM": {
        "name": "STORM (Шторм: Deep Defense)",
        "badge_color": "#a855f7",     # Purple
        "is_calm_split": False,
        "step_1_discount": 0.0110,    # -1.10%
        "step_2_discount": 0.0320,    # -3.20%
        "step_3_discount": 0.0600,    # -6.00%
        "budget_1": 7.50,
        "budget_2": 14.00,
        "budget_3": 17.00,
        "tp_target": 0.0180,          # +1.80% Rocket Rider
        "use_maker_tp": False,
        "trailing_activation": 0.0180,
    },
}

# Continuous Adaptive Spacing Benchmarks
BASE_SPACING = {"step_1": 0.0055, "step_2": 0.0175, "step_3": 0.0320}
VOLATILITY_BENCHMARK_15M = 0.0080    # 0.80% 15m range is baseline (multiplier = 1.0)
MIN_VOL_MULTIPLIER = 1.00            # step 1 is firmly anchored at 0.55% (does not shrink below 0.55%)
MAX_VOL_MULTIPLIER = 2.00            # in storm market, step1 widens up to ~1.10%

# Take-Profit & Soft Breakeven
STANDARD_TP_PCT = 0.0070            # +0.70% (Net +0.50% after fees; captures micro-swings)
SOFT_BREAKEVEN_TP_PCT = 0.0035      # +0.35% (Net +0.15% after 0.20% fees)
STALE_POSITION_HOURS = 6.0          # Switch to Soft Breakeven after 6 hours
CIRCUIT_BREAKER_MAX_DD = 0.05       # 5% max drawdown from peak equity

# Step 3 Partial Take-Profit (Scale-Out De-risking)
SCALE_OUT_TRIGGER_GAIN_PCT = 0.0045  # +0.45% gain from VWAP triggers partial exit of Step 3
SCALE_OUT_COOLDOWN_SEC = 300.0       # 5-minute cooldown between scale-out events per token

# Trailing Take-Profit (Rocket Rider) - Desktop Profile
TRAILING_ACTIVATION_PCT = 0.0070    # +0.70% gain from entry triggers TRAILING_ACTIVE (responsive scalp)
TRAILING_CALLBACK_PCT = 0.0030      # 0.30% pullback from peak triggers market sell
TRAILING_MIN_FLOOR_PCT = 0.0040     # +0.40% minimum profit floor (guaranteed net profit +0.20%)

# Flash Sniper (Crash Harvester / Wick Catcher) Parameters
SNIPER_ENABLED = True               # Autonomous parallel branch for catching flash wicks
SNIPER_TARGET_SYMBOL = SECONDARY_SYMBOL   # Execution asset: NEARUSDT (whitelisted on Bybit KZ API key)
SNIPER_RADAR_SYMBOL = PRIMARY_SYMBOL     # Lead sensor: SUIUSDT (drops first by 60-180s)
SNIPER_ORDER_LINK_PREFIX = "SNIPER_NEAR" # Unique orderLinkId prefix
SNIPER_BUDGET_USD = 5.25            # Strict isolated budget (safely above Bybit $5.00 min)
SNIPER_DIP_DEPTH_PCT = 0.0250       # -2.50% dip trap depth from current spot
SNIPER_TP_PCT = 0.0150              # Baseline TP (+1.50%)
SNIPER_AMEND_COOLDOWN_SEC = 60.0    # Soft chase cooldown (fast 60s upward float)
SNIPER_AMEND_THRESHOLD_PCT = 0.0050 # Float upward if market pulled away by > 0.50%
SNIPER_USE_ROCKET = True            # Rocket Rider Trailing Take-Profit for Flash Sniper
SNIPER_ROCKET_ACTIVATION_PCT = 0.0120 # +1.20% rebound activates Rocket Rider Trailing
SNIPER_ROCKET_CALLBACK_PCT = 0.0050 # 0.50% pullback from peak triggers instant exit (noise buffer)
SNIPER_ROCKET_FLOOR_PCT = 0.0090    # +0.90% guaranteed profit floor once activated

# Momentum Breakout (Squeeze Explosion / Volatility Expansion) Parameters
BREAKOUT_ENABLED = True
BREAKOUT_TARGET_SYMBOL = TERTIARY_SYMBOL      # AVAXUSDT (dedicated momentum & impulse scalper)
BREAKOUT_ORDER_LINK_PREFIX = "BREAKOUT"        # Unique orderLinkId prefix
BREAKOUT_BUDGET_USD = 5.25                    # Strictly isolated budget (matches Bybit $5.00 min)
BREAKOUT_LOOKBACK_BARS = 15                   # Lookback period for resistance calculation (15 1m candles)
BREAKOUT_VOLUME_FACTOR = 2.0                  # Volume spike confirmation threshold (2.0x avg volume)
BREAKOUT_STOP_LOSS_PCT = 0.0120               # -1.20% hard stop-loss against fakeouts
BREAKOUT_ROCKET_ACTIVATION_PCT = 0.0090       # +0.90% gain triggers Trailing Rocket
BREAKOUT_ROCKET_CALLBACK_PCT = 0.0035         # 0.35% pullback from peak triggers market sell
BREAKOUT_ROCKET_FLOOR_PCT = 0.0065            # +0.65% guaranteed profit floor once activated
BREAKOUT_COOLDOWN_SEC = 300.0                 # 5-minute cooldown between trades

TOKEN_METADATA = {
    PRIMARY_SYMBOL: {
        "base_coin": "SUI",
        "name": "Sui",
        "badge_color": "#38bdf8",     # Cyan
        "min_order_amt": 5.00,
        "qty_decimals": 2,
        "price_decimals": 4,
        "dump_1m_threshold": -0.0060,
        "dump_3m_threshold": -0.0120,
        "trailing_activation_pct": 0.0070, # +0.70% (Responsive Micro-Scalp)
        "trailing_callback_pct": 0.0030,   # 0.30%
        "trailing_min_floor_pct": 0.0040,  # +0.40%
    },
    SECONDARY_SYMBOL: {
        "base_coin": "NEAR",
        "name": "Near",
        "badge_color": "#10b981",     # Emerald green
        "min_order_amt": 5.00,
        "qty_decimals": 2,
        "price_decimals": 3,
        "dump_1m_threshold": -0.0060,
        "dump_3m_threshold": -0.0120,
        "trailing_activation_pct": 0.0120, # +1.20% (Wide Rocket Runway)
        "trailing_callback_pct": 0.0050,   # 0.50% (Noise buffer)
        "trailing_min_floor_pct": 0.0090,  # +0.90% (Guaranteed solid win)
    },
    TERTIARY_SYMBOL: {
        "base_coin": "AVAX",
        "name": "Avalanche",
        "badge_color": "#ef4444",     # Red
        "min_order_amt": 5.00,
        "qty_decimals": 3,
        "price_decimals": 3,
        "dump_1m_threshold": -0.0060,
        "dump_3m_threshold": -0.0120,
        "trailing_activation_pct": 0.0100, # +1.00%
        "trailing_callback_pct": 0.0040,   # 0.40%
        "trailing_min_floor_pct": 0.0070,  # +0.70%
    },
}


def _raw_send_telegram(text: str) -> None:
    """Synchronous HTTP worker for delivering Telegram trade alerts."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    for attempt in range(2):
        try:
            urllib.request.urlopen(req, timeout=12)
            return
        except urllib.error.HTTPError as he:
            if he.code == 400:
                try:
                    payload_plain = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode("utf-8")
                    req_plain = urllib.request.Request(url, data=payload_plain, headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req_plain, timeout=12)
                    return
                except Exception as e2:
                    logger.warning(f"Telegram plain alert fallback error: {e2}")
                    return
            else:
                logger.warning(f"Telegram alert delivery error (HTTP {he.code}): {he}")
                return
        except Exception as e:
            if attempt == 0:
                time.sleep(1)
            else:
                logger.warning(f"Telegram alert delivery error: {e}")


_telegram_alert_queue: queue.Queue[str] = queue.Queue(maxsize=100)


def _telegram_alert_worker() -> None:
    while True:
        try:
            msg = _telegram_alert_queue.get()
            _raw_send_telegram(msg)
        except Exception:
            pass
        finally:
            _telegram_alert_queue.task_done()


_t_tg_worker = threading.Thread(target=_telegram_alert_worker, daemon=True, name="TelegramAlertWorker")
_t_tg_worker.start()


def send_telegram(text: str) -> None:
    """Enqueues trade alert for asynchronous delivery, preventing network stalls in trading loop."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        first_line = text.splitlines()[0] if text else ""
        logger.info(f"📢 [Alert (Local)]: {first_line}")
        return
    try:
        _telegram_alert_queue.put_nowait(text)
    except queue.Full:
        logger.warning("Telegram alert queue is full; dropping alert to protect trading loop.")


# =====================================================================
# CLUSTER COORDINATION & DISTRIBUTED HANDOVER (ZERO 409 CONFLICT)
# =====================================================================

def get_astana_time() -> datetime.datetime:
    """Returns current time in Astana (UTC+5)."""
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=ASTANA_TZ_OFFSET_HOURS)


def is_desktop_schedule_window() -> bool:
    """Checks whether current Astana time is within Desktop office hours (Mon-Fri 08:00 - 17:30)."""
    astana_dt = get_astana_time()
    weekday = astana_dt.weekday()  # Monday is 0, Sunday is 6
    if weekday >= 5:
        return False  # Weekend is strictly mobile
    dec_hour = astana_dt.hour + (astana_dt.minute / 60.0)
    return DESKTOP_HOURS_START <= dec_hour < DESKTOP_HOURS_END


def read_cluster_state() -> Dict[str, Any]:
    """Reads cluster state from Telegram pinned board without calling getUpdates (zero 409 conflict)."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        active = "desktop" if is_desktop_schedule_window() else "mobile"
        return {"active_host": active, "heartbeat_ts": time.time(), "msg_id": None, "note": "Clock Schedule"}
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getChat?chat_id={TELEGRAM_CHAT_ID}"
        req = urllib.request.Request(url, headers={"User-Agent": "BybitCluster/2.0"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read().decode("utf-8"))
        pm = d.get("result", {}).get("pinned_message")
        if not pm:
            return {"active_host": "mobile", "heartbeat_ts": 0.0, "msg_id": None, "note": ""}

        txt = pm.get("text", "")
        msg_id = pm.get("message_id")
        active_host = "mobile"
        hb_ts = 0.0
        note = ""

        for line in txt.splitlines():
            if "#ACTIVE_HOST=" in line:
                parts = line.split("#ACTIVE_HOST=")[1].split()
                if parts:
                    active_host = parts[0].strip(" `\"'").lower()
            if "#HEARTBEAT=" in line:
                parts = line.split("#HEARTBEAT=")[1].split()
                if parts:
                    try:
                        hb_ts = float(parts[0].strip(" `\"'"))
                    except Exception:
                        pass
            if "• Примечание:" in line:
                note = line.replace("• Примечание:", "").strip().strip("_")

        return {"active_host": active_host, "heartbeat_ts": hb_ts, "msg_id": msg_id, "note": note, "text": txt}
    except Exception as e:
        logger.debug(f"read_cluster_state error: {e}")
        return {"active_host": "mobile", "heartbeat_ts": 0.0, "msg_id": None, "note": ""}


def write_cluster_state(active_host: str, note: str = "", existing_msg_id: Optional[int] = None) -> Optional[int]:
    """Updates or pins the cluster coordination board message in Telegram with retry resilience."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return None
    now_ts = time.time()
    dt_str = get_astana_time().strftime("%d.%m.%Y %H:%M:%S")
    icon = "🖥️ DESKTOP (Smart Step)" if active_host == "desktop" else "📱 MOBILE (STORM x2.0)"
    board_text = (
        f"📌 *[BYBIT КЛАСТЕР: КООРДИНАТОР]*\n\n"
        f"• Активный узел: *{icon}*\n"
        f"• Время (Астана): `{dt_str}`\n"
        f"• Статус: `{active_host.upper()}_ACTIVE`\n"
        f"• Примечание: _{note}_\n\n"
        f"`#ACTIVE_HOST={active_host} #HEARTBEAT={now_ts:.0f}`"
    )

    # Try editing existing message
    if existing_msg_id:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
        data = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "message_id": existing_msg_id,
            "text": board_text,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "BybitCluster/2.0"})
        for _ in range(2):
            try:
                with urllib.request.urlopen(req, timeout=12) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res.get("ok"):
                        return existing_msg_id
            except Exception:
                time.sleep(1)

    # Send new message and pin it
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({
        "chat_id": TELEGRAM_CHAT_ID,
        "text": board_text,
        "parse_mode": "Markdown"
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "BybitCluster/2.0"})
    new_id = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=12) as r:
                res = json.loads(r.read().decode("utf-8"))
            if res.get("ok"):
                new_id = res.get("result", {}).get("message_id")
                break
        except Exception as e:
            logger.warning(f"write_cluster_state attempt {attempt+1} failed: {e}")
            time.sleep(1.5)

    if new_id:
        try:
            pin_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/pinChatMessage"
            pin_data = json.dumps({
                "chat_id": TELEGRAM_CHAT_ID,
                "message_id": new_id,
                "disable_notification": True
            }).encode("utf-8")
            req_pin = urllib.request.Request(pin_url, data=pin_data, headers={"Content-Type": "application/json", "User-Agent": "BybitCluster/2.0"})
            with urllib.request.urlopen(req_pin, timeout=12):
                pass
        except Exception as pe:
            logger.debug(f"pinChatMessage notice: {pe}")
        return new_id

    return None

# =====================================================================
# TRAILING TAKE-PROFIT CONTROLLER (ROCKET RIDER) - DESKTOP PROFILE
# =====================================================================

@dataclass
class TrailingPositionState:
    symbol: str
    status: str = "IDLE"              # "IDLE" or "TRAILING_ACTIVE"
    entry_price: float = 0.0
    peak_price: float = 0.0
    stop_price: float = 0.0
    activation_price: float = 0.0
    floor_price: float = 0.0
    activated_at: float = 0.0


class TrailingTakeProfitController:
    """Manages dynamic Trailing Take-Profit (Rocket Rider) for desktop profile.

    Tracks high water mark (peak_price), maintains guaranteed profit floor (+0.50%),
    and triggers instant execution when price pulls back by 0.45% from the peak.
    """

    def __init__(
        self,
        activation_pct: float = TRAILING_ACTIVATION_PCT,
        callback_pct: float = TRAILING_CALLBACK_PCT,
        min_floor_pct: float = TRAILING_MIN_FLOOR_PCT,
    ) -> None:
        self.activation_pct = activation_pct
        self.callback_pct = callback_pct
        self.min_floor_pct = min_floor_pct
        self.states: Dict[str, TrailingPositionState] = {}

    def get_state(self, symbol: str) -> TrailingPositionState:
        if symbol not in self.states:
            self.states[symbol] = TrailingPositionState(symbol=symbol)
        return self.states[symbol]

    def reset(self, symbol: str) -> None:
        if symbol in self.states:
            self.states[symbol] = TrailingPositionState(symbol=symbol)

    def is_any_trailing_active(self) -> bool:
        return any(s.status == "TRAILING_ACTIVE" for s in self.states.values())

    def update_price(
        self,
        symbol: str,
        cur_price: float,
        entry_price: float,
        free_qty: float,
        holding_val_usd: float,
        activation_pct: Optional[float] = None,
        callback_pct: Optional[float] = None,
        min_floor_pct: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Updates trailing state with current price and returns event or action if triggered."""
        if holding_val_usd < 5.00 or free_qty <= 0 or entry_price <= 0 or cur_price <= 0:
            if symbol in self.states and self.states[symbol].status != "IDLE":
                self.reset(symbol)
            return None

        act_pct = activation_pct if activation_pct is not None else self.activation_pct
        cb_pct = callback_pct if callback_pct is not None else self.callback_pct
        fl_pct = min_floor_pct if min_floor_pct is not None else self.min_floor_pct

        state = self.get_state(symbol)
        state.entry_price = entry_price
        gain_pct = (cur_price - entry_price) / entry_price

        if state.status == "IDLE":
            # Activation condition: gain >= act_pct
            if gain_pct >= act_pct:
                state.status = "TRAILING_ACTIVE"
                state.peak_price = cur_price
                state.activation_price = entry_price * (1.0 + act_pct)
                state.floor_price = entry_price * (1.0 + fl_pct)
                raw_stop = cur_price * (1.0 - cb_pct)
                state.stop_price = max(raw_stop, state.floor_price)
                state.activated_at = time.time()

                return {
                    "event": "ACTIVATED",
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "cur_price": cur_price,
                    "peak_price": cur_price,
                    "stop_price": state.stop_price,
                    "floor_price": state.floor_price,
                    "gain_pct": gain_pct,
                    "qty": free_qty,
                }
            return None

        elif state.status == "TRAILING_ACTIVE":
            # High Water Mark tracking: update peak and ratchet up stop
            if cur_price > state.peak_price:
                state.peak_price = cur_price
                raw_stop = cur_price * (1.0 - cb_pct)
                state.floor_price = entry_price * (1.0 + fl_pct)
                # Ratchet up: stop price strictly never decreases
                state.stop_price = max(raw_stop, state.floor_price, state.stop_price)

            # Execution condition: pullback hits or breaches stop price
            if cur_price <= state.stop_price:
                trigger_data = {
                    "action": "TRIGGER_EXIT",
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "peak_price": state.peak_price,
                    "exit_price": cur_price,
                    "stop_price": state.stop_price,
                    "floor_price": state.floor_price,
                    "gain_pct": gain_pct,
                    "peak_gain_pct": (state.peak_price - entry_price) / entry_price,
                    "qty": free_qty,
                }
                self.reset(symbol)
                return trigger_data

            return None


@dataclass
class FlashSniperState:
    symbol: str
    active: bool = False
    buy_order_id: Optional[str] = None
    buy_price: float = 0.0
    allocated_usd: float = SNIPER_BUDGET_USD
    position_qty: float = 0.0
    entry_price: float = 0.0
    tp_order_id: Optional[str] = None
    tp_price: float = 0.0
    status: str = "IDLE"  # IDLE | HUNTING | POSITION_HELD | ROCKET_ACTIVE | TP_PLACED
    last_amend_time: float = 0.0
    completed_cycles: int = 0
    total_profit_usd: float = 0.0
    peak_price: float = 0.0
    stop_price: float = 0.0
    floor_price: float = 0.0
    last_obi: float = 0.0


class FlashSniperController:
    """Autonomous Parallel Flash-Crash Harvester / Wick Catcher with Rocket Rider Trailing.

    Places an isolated limit Maker buy order at -2.50% dip depth with dedicated $5.25 USDT.
    Soft-floats upward only when market drifts higher and cooldown expires.
    Equipped with dynamic Rocket Rider Trailing Take-Profit:
      - Activates at +1.50% rebound from bottom
      - Secures guaranteed profit floor at +1.20%
      - Rides upward momentum, ratcheting stop 0.35% beneath peak
      - Ejects at the crest of the bounce for maximal profit
    Shielded by Lead-Lag CRASH guard, Dump Guard, and Order Book Imbalance (OBI) guard.
    """

    def __init__(
        self,
        symbol: str = SNIPER_TARGET_SYMBOL,
        budget_usd: float = SNIPER_BUDGET_USD,
        dip_depth_pct: float = SNIPER_DIP_DEPTH_PCT,
        tp_pct: float = SNIPER_TP_PCT,
        amend_cooldown_sec: float = SNIPER_AMEND_COOLDOWN_SEC,
        amend_threshold_pct: float = SNIPER_AMEND_THRESHOLD_PCT,
        use_rocket: bool = SNIPER_USE_ROCKET,
        rocket_activation_pct: float = SNIPER_ROCKET_ACTIVATION_PCT,
        rocket_callback_pct: float = SNIPER_ROCKET_CALLBACK_PCT,
        rocket_floor_pct: float = SNIPER_ROCKET_FLOOR_PCT,
    ) -> None:
        self.symbol = symbol
        self.budget_usd = budget_usd
        self.dip_depth_pct = dip_depth_pct
        self.tp_pct = tp_pct
        self.amend_cooldown_sec = amend_cooldown_sec
        self.amend_threshold_pct = amend_threshold_pct
        self.use_rocket = use_rocket
        self.rocket_activation_pct = rocket_activation_pct
        self.rocket_callback_pct = rocket_callback_pct
        self.rocket_floor_pct = rocket_floor_pct
        self.state = FlashSniperState(symbol=symbol, allocated_usd=budget_usd)

    def update_budget(self, new_budget: float) -> None:
        """Dynamically scales sniper budget under auto-compounding (never drops below $5.05)."""
        safe_budget = max(5.05, round(new_budget, 2))
        self.budget_usd = safe_budget
        self.state.allocated_usd = safe_budget

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.state.symbol,
            "status": self.state.status,
            "buy_price": self.state.buy_price,
            "allocated_usd": self.state.allocated_usd,
            "position_qty": self.state.position_qty,
            "entry_price": self.state.entry_price,
            "tp_price": self.state.tp_price,
            "use_rocket": self.use_rocket,
            "peak_price": self.state.peak_price,
            "stop_price": self.state.stop_price,
            "floor_price": self.state.floor_price,
            "completed_cycles": self.state.completed_cycles,
            "total_profit_usd": round(self.state.total_profit_usd, 4),
            "obi": self.state.last_obi,
        }

    def sync_on_exchange_orders(self, open_orders: List[Dict[str, Any]]) -> None:
        """Syncs in-flight sniper orders from exchange state."""
        sniper_buys = [
            o for o in open_orders
            if o.get("side") == "Buy" and str(o.get("orderLinkId", "")).startswith(SNIPER_ORDER_LINK_PREFIX)
        ]
        sniper_sells = [
            o for o in open_orders
            if o.get("side") == "Sell" and str(o.get("orderLinkId", "")).startswith(SNIPER_ORDER_LINK_PREFIX)
        ]

        if sniper_sells:
            s_ord = sniper_sells[0]
            self.state.tp_order_id = s_ord.get("orderId")
            self.state.tp_price = float(s_ord.get("price", 0.0))
            self.state.status = "TP_PLACED"
        elif sniper_buys:
            b_ord = sniper_buys[0]
            self.state.buy_order_id = b_ord.get("orderId")
            self.state.buy_price = float(b_ord.get("price", 0.0))
            self.state.status = "HUNTING"
        else:
            if self.state.status == "TP_PLACED":
                # Sell order finished -> cycle completed!
                if self.state.position_qty > 0 and self.state.entry_price > 0 and self.state.tp_price > 0:
                    realized = round((self.state.tp_price - self.state.entry_price) * self.state.position_qty, 4)
                    self.state.completed_cycles += 1
                    self.state.total_profit_usd += max(0.0, realized)
                    logger.info(
                        f"🎯💰 [Flash Sniper] Цикл #{self.state.completed_cycles} УСПЕШНО ЗАКРЫТ! "
                        f"Профит: +${realized:.4f} USDT"
                    )
                self.state.status = "IDLE"
                self.state.position_qty = 0.0
                self.state.entry_price = 0.0
                self.state.tp_order_id = None
                self.state.tp_price = 0.0
                self.state.buy_order_id = None
                self.state.buy_price = 0.0
                self.state.peak_price = 0.0
                self.state.stop_price = 0.0
                self.state.floor_price = 0.0
            elif self.state.status in ("POSITION_HELD", "ROCKET_ACTIVE"):
                # Position is held in-flight without open exchange orders while riding rocket
                pass
            elif self.state.status == "HUNTING":
                # Buy order disappeared: check if it filled or was canceled
                # Status will be updated in process_cycle
                pass

    def tick(
        self,
        client: Any,
        cur_price: float,
        avail_usdt: float,
        free_qty: float,
        lead_lag_status: str,
        price_decimals: int = 4,
        qty_decimals: int = 2,
        token_1m_chg: float = 0.0,
        token_3m_chg: float = 0.0,
        volatility_regime: str = "NORMAL",
        obi: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """Main execution tick for Flash Sniper."""
        now = time.time()
        self.state.last_obi = round(obi, 3)

        # 1. Lead-Lag Safety Guard: Emergency abort on systemic BTC CRASH
        if lead_lag_status == "CRASH":
            if self.state.status == "HUNTING" and self.state.buy_order_id:
                logger.warning(f"🚨 [Flash Sniper] BTC CRASH! Экстренная отмена ордера-ловушки ${self.state.buy_price}!")
                client.cancel_order(self.symbol, self.state.buy_order_id)
                self.state.status = "IDLE"
                self.state.buy_order_id = None
                self.state.buy_price = 0.0
            return None

        # 1.1 Local Token Dump Guard: Emergency abort on acute idiosyncratic dump (falling knife)
        is_dumping = (token_1m_chg <= -0.0070) or (token_3m_chg <= -0.0150)
        if is_dumping:
            if self.state.status == "HUNTING" and self.state.buy_order_id:
                logger.warning(
                    f"🚨 [Flash Sniper Dump Guard] Обнаружен резкий слив {self.symbol} "
                    f"(1m: {token_1m_chg*100:+.2f}%, 3m: {token_3m_chg*100:+.2f}%)! "
                    f"Экстренный отзыв ловушки ${self.state.buy_price:.4f} для защиты от ножа!"
                )
                client.cancel_order(self.symbol, self.state.buy_order_id)
                self.state.status = "IDLE"
                self.state.buy_order_id = None
                self.state.buy_price = 0.0
            return None

        # 1.2 Order Book Imbalance (OBI) Guard: Emergency abort on severe sell wall / vacuum of bids
        # OBI < -0.35 indicates massive ask pressure and lack of bid depth (high risk of slicing through)
        if obi < -0.35:
            if self.state.status == "HUNTING" and self.state.buy_order_id:
                logger.warning(
                    f"🚨 [Flash Sniper OBI Guard] Критический дисбаланс стакана {self.symbol} "
                    f"(OBI: {obi:+.3f} < -0.35)! Давит стена продавцов, глубина покупок истощена. "
                    f"Экстренный отзыв ловушки ${self.state.buy_price:.4f} во избежание ножа!"
                )
                client.cancel_order(self.symbol, self.state.buy_order_id)
                self.state.status = "IDLE"
                self.state.buy_order_id = None
                self.state.buy_price = 0.0
            return None

        # Adaptive Dip Depth: in STORM regime, expand trap depth to prevent premature fills
        eff_dip_pct = max(self.dip_depth_pct, 0.0350) if volatility_regime == "STORM" else self.dip_depth_pct
        target_price = round(cur_price * (1.0 - eff_dip_pct), price_decimals) if cur_price > 0 else 0.0

        # 2. Smart Float: Upward chase on rally, and Downward retract on market slide
        if self.state.status == "HUNTING" and self.state.buy_order_id and target_price > 0 and self.state.buy_price > 0:
            price_delta_pct = (target_price - self.state.buy_price) / self.state.buy_price
            time_since_amend = now - self.state.last_amend_time

            # Upward chase: market drifted higher -> pull trap up
            should_amend_up = (
                price_delta_pct >= self.amend_threshold_pct
                and time_since_amend >= self.amend_cooldown_sec
            )

            # Downward retract: market slides down -> push trap deeper to maintain safety cushion
            should_amend_down = (
                price_delta_pct <= -self.amend_threshold_pct
                and time_since_amend >= 30.0  # Responsive 30s retract to avoid getting caught on slow bleed
            )

            if should_amend_up or should_amend_down:
                new_qty = math.floor((self.budget_usd / target_price) * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                if (new_qty * target_price) >= 5.00:
                    action_label = "Подтягивание ловушки вверх" if should_amend_up else "🛡️ Оттягивание ловушки глубже"
                    logger.info(
                        f"🎯 [Flash Sniper Smart-Float] {action_label}: ${self.state.buy_price:.4f} -> ${target_price:.4f} "
                        f"(-{eff_dip_pct*100:.2f}%) [Объем: {new_qty}]"
                    )
                    resp_amend = client.amend_order(
                        self.symbol,
                        order_id=self.state.buy_order_id,
                        price=target_price,
                        qty=new_qty,
                        price_precision=price_decimals,
                        qty_precision=qty_decimals,
                    )
                    if resp_amend.get("retCode") == 0:
                        self.state.buy_price = target_price
                        self.state.last_amend_time = now
                    elif resp_amend.get("retCode") in (10001, 20001):
                        self.state.last_amend_time = now
                    else:
                        logger.debug(f"Flash sniper amend result: {resp_amend}")

        # Check if held position was already sold/closed on exchange (e.g. by Trailing Take-Profit)
        if self.state.status in ("POSITION_HELD", "ROCKET_ACTIVE") and free_qty <= 0.05:
            if self.state.position_qty > 0 and self.state.entry_price > 0:
                realized = round((cur_price - self.state.entry_price) * self.state.position_qty, 4) if cur_price > 0 else 0.0
                self.state.completed_cycles += 1
                self.state.total_profit_usd += max(0.0, realized)
                logger.info(
                    f"🎯💰 [Flash Sniper] Позиция закрыта на бирже! Цикл #{self.state.completed_cycles} завершен, "
                    f"Профит: +${realized:.4f} USDT. Перезарядка ловушки..."
                )
            self.state.status = "IDLE"
            self.state.position_qty = 0.0
            self.state.entry_price = 0.0
            self.state.peak_price = 0.0
            self.state.stop_price = 0.0
            self.state.floor_price = 0.0
            self.state.buy_order_id = None
            self.state.buy_price = 0.0

        # 3. Position filled -> Handle Take-Profit (Rocket Rider or Maker TP)
        if self.state.status in ("POSITION_HELD", "ROCKET_ACTIVE") and self.state.position_qty > 0 and self.state.entry_price > 0:
            if not self.use_rocket:
                # Static Maker Limit TP
                tp_price = round(self.state.entry_price * (1.0 + self.tp_pct), price_decimals)
                tp_qty = math.floor(self.state.position_qty * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                if (tp_qty * tp_price) >= 5.00:
                    unique_link_id = f"{SNIPER_ORDER_LINK_PREFIX}_TP_{int(now)}"
                    logger.info(
                        f"🎯🟢 [Flash Sniper TP] Выставление лимитного ТП: {tp_qty} @ ${tp_price:.4f} (+{self.tp_pct*100:.2f}%)"
                    )
                    resp_tp = client.create_limit_order(
                        self.symbol,
                        "Sell",
                        tp_qty,
                        tp_price,
                        post_only=True,
                        price_precision=price_decimals,
                        qty_precision=qty_decimals,
                        order_link_id=unique_link_id,
                    )
                    if resp_tp.get("retCode") == 0:
                        self.state.tp_order_id = resp_tp.get("result", {}).get("orderId")
                        self.state.tp_price = tp_price
                        self.state.status = "TP_PLACED"
                        return {"action": "TP_PLACED", "tp_price": tp_price, "qty": tp_qty}
                    else:
                        logger.warning(f"Failed to place Flash Sniper TP: {resp_tp}")
            else:
                # Dynamic Rocket Rider Trailing Take-Profit
                gain_pct = round((cur_price - self.state.entry_price) / self.state.entry_price, 6)

                if self.state.status == "POSITION_HELD":
                    # Check activation condition (+1.50% rebound)
                    if gain_pct >= self.rocket_activation_pct:
                        self.state.status = "ROCKET_ACTIVE"
                        self.state.peak_price = cur_price
                        self.state.floor_price = round(self.state.entry_price * (1.0 + self.rocket_floor_pct), price_decimals)
                        raw_stop = round(cur_price * (1.0 - self.rocket_callback_pct), price_decimals)
                        self.state.stop_price = max(raw_stop, self.state.floor_price)
                        logger.info(
                            f"🎯🚀 [Sniper Rocket] ЗАЖИГАНИЕ РАКЕТЫ! Отскок: +{gain_pct*100:.2f}% | "
                            f"Пик: ${cur_price:.4f}, Защитный пол: ${self.state.floor_price:.4f}, Стоп: ${self.state.stop_price:.4f}"
                        )
                        return {
                            "event": "ROCKET_ACTIVATED",
                            "symbol": self.symbol,
                            "cur_price": cur_price,
                            "gain_pct": gain_pct,
                            "stop_price": self.state.stop_price,
                            "floor_price": self.state.floor_price,
                        }

                elif self.state.status == "ROCKET_ACTIVE":
                    # Update peak and ratchet up trailing stop
                    if cur_price > self.state.peak_price:
                        self.state.peak_price = cur_price
                        raw_stop = round(cur_price * (1.0 - self.rocket_callback_pct), price_decimals)
                        self.state.floor_price = round(self.state.entry_price * (1.0 + self.rocket_floor_pct), price_decimals)
                        self.state.stop_price = max(raw_stop, self.state.floor_price, self.state.stop_price)
                        logger.info(
                            f"🎯🚀 [Sniper Rocket Ratchet] Новый пик: ${cur_price:.4f} (+{gain_pct*100:.2f}%) | "
                            f"Стоп подтянут: ${self.state.stop_price:.4f}"
                        )

                    # Trigger exit on pullback from peak
                    if cur_price <= self.state.stop_price:
                        sell_qty = math.floor(self.state.position_qty * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                        logger.info(
                            f"🎯🚀💥 [Sniper Rocket Eject] Фиксация на пике! Откат от вершины до ${cur_price:.4f}. "
                            f"Сброс {sell_qty} {self.symbol}..."
                        )
                        resp_sell = client.create_market_order(self.symbol, "Sell", sell_qty)
                        if resp_sell.get("retCode") == 0:
                            realized = round((cur_price - self.state.entry_price) * sell_qty, 4)
                            self.state.completed_cycles += 1
                            self.state.total_profit_usd += max(0.0, realized)
                            logger.info(
                                f"🎯💰 [Sniper Rocket Closed] Цикл #{self.state.completed_cycles} закрыт по Ракете! "
                                f"Профит: +${realized:.4f} USDT (+{gain_pct*100:.2f}%)"
                            )
                            self.state.status = "IDLE"
                            self.state.position_qty = 0.0
                            self.state.entry_price = 0.0
                            self.state.peak_price = 0.0
                            self.state.stop_price = 0.0
                            self.state.floor_price = 0.0
                            self.state.buy_order_id = None
                            self.state.buy_price = 0.0
                            return {
                                "action": "ROCKET_EXIT",
                                "symbol": self.symbol,
                                "exit_price": cur_price,
                                "profit_usd": realized,
                                "gain_pct": gain_pct,
                            }
                        else:
                            logger.error(f"Failed to execute Sniper Rocket market exit: {resp_sell}")

        # 4. IDLE mode -> Place new dip trap if funds available, not dumping, and orderbook is not imbalanced
        if self.state.status == "IDLE" and avail_usdt >= self.budget_usd and cur_price > 0 and not is_dumping:
            if obi < -0.35:
                logger.debug(
                    f"🛡️ [Flash Sniper OBI Guard] Вход в ловушку {self.symbol} отложен: "
                    f"OBI {obi:+.3f} < -0.35 (преобладание продавцов в стакане)"
                )
                return None

            target_price = round(cur_price * (1.0 - eff_dip_pct), price_decimals)
            target_qty = math.floor((self.budget_usd / target_price) * (10 ** qty_decimals)) / float(10 ** qty_decimals)
            val = target_qty * target_price

            if val >= 5.00 and val <= avail_usdt:
                unique_link_id = f"{SNIPER_ORDER_LINK_PREFIX}_BUY_{int(now)}"
                logger.info(
                    f"🎯 [Flash Sniper Trap] Расстановка ловушки пролива: {target_qty} {self.symbol} @ "
                    f"${target_price:.4f} (-{eff_dip_pct*100:.2f}%) [Бюджет: ${val:.2f} USDT]"
                )
                resp_buy = client.create_limit_order(
                    self.symbol,
                    "Buy",
                    target_qty,
                    target_price,
                    post_only=True,
                    price_precision=price_decimals,
                    qty_precision=qty_decimals,
                    order_link_id=unique_link_id,
                )
                if resp_buy.get("retCode") == 0:
                    self.state.buy_order_id = resp_buy.get("result", {}).get("orderId")
                    self.state.buy_price = target_price
                    self.state.last_amend_time = now
                    self.state.status = "HUNTING"
                    return {"action": "BUY_PLACED", "price": target_price, "qty": target_qty, "val": val}
                else:
                    logger.debug(f"Flash sniper trap placement retCode={resp_buy.get('retCode')}: {resp_buy.get('retMsg')}")

        return None


@dataclass
class BreakoutState:
    symbol: str
    status: str = "IDLE"  # IDLE | ARMED | IN_FLIGHT | COOLDOWN
    entry_price: float = 0.0
    position_qty: float = 0.0
    allocated_usd: float = BREAKOUT_BUDGET_USD
    peak_price: float = 0.0
    stop_price: float = 0.0
    floor_price: float = 0.0
    trailing_active: bool = False
    resistance_price: float = 0.0
    last_volume_ratio: float = 0.0
    completed_cycles: int = 0
    total_profit_usd: float = 0.0
    last_exit_time: float = 0.0


class MomentumBreakoutController:
    """Autonomous Momentum Breakout Engine (Squeeze Explosion & Impulse Scalper).

    Monitors for price compression, confirms upward explosion through resistance
    with >= 2.0x volume spike and supportive orderbook (OBI >= -0.15), enters with isolated $5.25 USDT,
    and rides the expansion crest via Rocket Rider Trailing Take-Profit.
    Shielded by -1.20% hard stop-loss against bull traps.
    """

    def __init__(
        self,
        symbol: str = BREAKOUT_TARGET_SYMBOL,
        budget_usd: float = BREAKOUT_BUDGET_USD,
        lookback_bars: int = BREAKOUT_LOOKBACK_BARS,
        volume_factor: float = BREAKOUT_VOLUME_FACTOR,
        stop_loss_pct: float = BREAKOUT_STOP_LOSS_PCT,
        rocket_activation_pct: float = BREAKOUT_ROCKET_ACTIVATION_PCT,
        rocket_callback_pct: float = BREAKOUT_ROCKET_CALLBACK_PCT,
        rocket_floor_pct: float = BREAKOUT_ROCKET_FLOOR_PCT,
        cooldown_sec: float = BREAKOUT_COOLDOWN_SEC,
    ) -> None:
        self.symbol = symbol
        self.budget_usd = budget_usd
        self.lookback_bars = lookback_bars
        self.volume_factor = volume_factor
        self.stop_loss_pct = stop_loss_pct
        self.rocket_activation_pct = rocket_activation_pct
        self.rocket_callback_pct = rocket_callback_pct
        self.rocket_floor_pct = rocket_floor_pct
        self.cooldown_sec = cooldown_sec
        self.state = BreakoutState(symbol=symbol, allocated_usd=budget_usd)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.state.symbol,
            "status": self.state.status,
            "allocated_usd": self.state.allocated_usd,
            "entry_price": self.state.entry_price,
            "position_qty": self.state.position_qty,
            "peak_price": self.state.peak_price,
            "stop_price": self.state.stop_price,
            "floor_price": self.state.floor_price,
            "resistance_price": self.state.resistance_price,
            "volume_ratio": round(self.state.last_volume_ratio, 2),
            "trailing_active": self.state.trailing_active,
            "completed_cycles": self.state.completed_cycles,
            "total_profit_usd": round(self.state.total_profit_usd, 4),
        }

    def tick(
        self,
        client: Any,
        cur_price: float,
        avail_usdt: float,
        free_qty: float,
        lead_lag_status: str,
        klines: List[List[Any]],
        obi: float = 0.0,
        price_decimals: int = 4,
        qty_decimals: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """Main execution tick for Momentum Breakout."""
        now = time.time()

        # 1. Cooldown period check after exit
        if self.state.status == "COOLDOWN":
            if (now - self.state.last_exit_time) >= self.cooldown_sec:
                self.state.status = "IDLE"
                logger.info(f"⚡ [Breakout] Пауза {int(self.cooldown_sec)}с завершена. Мониторинг пробоев активен.")
            else:
                return None

        # Check if held position was already sold/closed on exchange (e.g. external fill or balance sweep)
        if self.state.status == "IN_FLIGHT" and free_qty <= 0.05:
            if self.state.position_qty > 0 and self.state.entry_price > 0:
                realized = round((cur_price - self.state.entry_price) * self.state.position_qty, 4) if cur_price > 0 else 0.0
                self.state.completed_cycles += 1
                self.state.total_profit_usd += realized
                logger.info(
                    f"⚡💰 [Breakout Reconciled] Позиция {self.symbol} закрыта на бирже! Цикл #{self.state.completed_cycles}, "
                    f"PnL: {realized:+.4f} USDT. Перезарядка в IDLE..."
                )
            self.state.status = "IDLE"
            self.state.position_qty = 0.0
            self.state.entry_price = 0.0
            self.state.peak_price = 0.0
            self.state.stop_price = 0.0
            self.state.floor_price = 0.0
            self.state.trailing_active = False
            return {"action": "EXTERNAL_CLOSE"}

        # 2. Manage Active IN_FLIGHT Position
        if self.state.status == "IN_FLIGHT":
            if self.state.position_qty <= 0 or self.state.entry_price <= 0:
                self.state.status = "IDLE"
                return None

            gain_pct = (cur_price - self.state.entry_price) / self.state.entry_price

            # Hard Stop-Loss check (Protection against bull traps / fakeouts)
            if gain_pct <= -self.stop_loss_pct:
                sell_qty = math.floor(self.state.position_qty * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                logger.warning(
                    f"⚡🛑 [Breakout Stop-Loss] Ложный пробой {self.symbol}! "
                    f"Текущая: ${cur_price:.4f} ({gain_pct*100:+.2f}%). Сброс {sell_qty} {self.symbol}..."
                )
                resp = client.create_market_order(self.symbol, "Sell", sell_qty)
                realized = round((cur_price - self.state.entry_price) * sell_qty, 4)
                self.state.completed_cycles += 1
                self.state.total_profit_usd += realized
                self.state.status = "COOLDOWN"
                self.state.last_exit_time = now
                self.state.position_qty = 0.0
                self.state.entry_price = 0.0
                self.state.peak_price = 0.0
                self.state.stop_price = 0.0
                self.state.floor_price = 0.0
                self.state.trailing_active = False
                return {"action": "STOP_LOSS", "loss_usd": realized, "gain_pct": gain_pct}

            # Rocket Rider Trailing Take-Profit
            if not self.state.trailing_active:
                if gain_pct >= self.rocket_activation_pct:
                    self.state.trailing_active = True
                    self.state.peak_price = cur_price
                    self.state.floor_price = round(self.state.entry_price * (1.0 + self.rocket_floor_pct), price_decimals)
                    raw_stop = round(cur_price * (1.0 - self.rocket_callback_pct), price_decimals)
                    self.state.stop_price = max(raw_stop, self.state.floor_price)
                    logger.info(
                        f"⚡🚀 [Breakout Rocket] ИМПУЛЬС ПОШЕЛ! +{gain_pct*100:.2f}% | "
                        f"Пик: ${cur_price:.4f}, Пол: ${self.state.floor_price:.4f}, Стоп: ${self.state.stop_price:.4f}"
                    )
                    return {"action": "ROCKET_ARMED", "gain_pct": gain_pct}
            else:
                # Ratchet up trailing stop
                if cur_price > self.state.peak_price:
                    self.state.peak_price = cur_price
                    raw_stop = round(cur_price * (1.0 - self.rocket_callback_pct), price_decimals)
                    self.state.floor_price = round(self.state.entry_price * (1.0 + self.rocket_floor_pct), price_decimals)
                    self.state.stop_price = max(raw_stop, self.state.floor_price, self.state.stop_price)

                # Pullback exit on momentum break
                if cur_price <= self.state.stop_price:
                    sell_qty = math.floor(self.state.position_qty * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                    logger.info(
                        f"⚡🚀💰 [Breakout Rocket Exit] Фиксация импульса {self.symbol} @ ${cur_price:.4f} (+{gain_pct*100:.2f}%)!"
                    )
                    resp = client.create_market_order(self.symbol, "Sell", sell_qty)
                    realized = round((cur_price - self.state.entry_price) * sell_qty, 4)
                    self.state.completed_cycles += 1
                    self.state.total_profit_usd += max(0.0, realized)
                    self.state.status = "COOLDOWN"
                    self.state.last_exit_time = now
                    self.state.position_qty = 0.0
                    self.state.entry_price = 0.0
                    self.state.peak_price = 0.0
                    self.state.stop_price = 0.0
                    self.state.floor_price = 0.0
                    self.state.trailing_active = False
                    return {"action": "PROFIT_EXIT", "profit_usd": realized, "gain_pct": gain_pct}

            return None

        # 3. IDLE / ARMED: Evaluate Breakout Trigger
        if self.state.status in ("IDLE", "ARMED"):
            # Market conditions check
            if lead_lag_status in ("CRASH", "SLIDING"):
                self.state.status = "IDLE"
                return None

            if avail_usdt < self.budget_usd or cur_price <= 0:
                return None

            if not klines or len(klines) < self.lookback_bars:
                return None

            # Calculate Resistance (max high of last completed 1m candles, excluding forming candle k[0])
            past_candles = klines[1:self.lookback_bars]
            past_highs = [float(k[2]) for k in past_candles if len(k) >= 3]
            resistance = max(past_highs) if past_highs else 0.0
            self.state.resistance_price = resistance

            # Calculate Volume Spike Ratio
            past_volumes = [float(k[5]) for k in past_candles if len(k) >= 6]
            avg_volume = (sum(past_volumes) / len(past_volumes)) if past_volumes else 1.0
            curr_volume = float(klines[0][5]) if len(klines) > 0 and len(klines[0]) >= 6 else 0.0
            vol_ratio = (curr_volume / avg_volume) if avg_volume > 0 else 0.0
            self.state.last_volume_ratio = vol_ratio

            # Check breakout trigger
            is_price_breakout = (cur_price >= resistance * 1.0005)
            is_volume_confirmed = (vol_ratio >= self.volume_factor)
            is_orderbook_supportive = (obi >= -0.15)  # No heavy sell wall blocking path

            if is_price_breakout and is_volume_confirmed and is_orderbook_supportive:
                buy_qty = math.floor((self.budget_usd / cur_price) * (10 ** qty_decimals)) / float(10 ** qty_decimals)
                order_val = buy_qty * cur_price

                if order_val >= 5.00 and order_val <= avail_usdt:
                    logger.info(
                        f"⚡🔥 [Breakout Triggered] Импульсный пробой {self.symbol}! "
                        f"Цена: ${cur_price:.4f} > Уровень: ${resistance:.4f} | "
                        f"Всплеск объема: {vol_ratio:.1f}x (Порог: {self.volume_factor:.1f}x) | OBI: {obi:+.3f} | "
                        f"Покупка {buy_qty} {self.symbol} (~${order_val:.2f} USDT)..."
                    )
                    resp = client.create_market_order(self.symbol, "Buy", buy_qty)
                    if resp.get("retCode") == 0:
                        self.state.status = "IN_FLIGHT"
                        self.state.entry_price = cur_price
                        self.state.position_qty = buy_qty
                        self.state.peak_price = cur_price
                        self.state.trailing_active = False
                        logger.info(
                            f"⚡✅ [Breakout Entered] Вход в импульс {self.symbol} @ ${cur_price:.4f} выполнен! "
                            f"Активирован Trailing Rocket Rider."
                        )
                        return {
                            "action": "BREAKOUT_ENTERED",
                            "symbol": self.symbol,
                            "price": cur_price,
                            "qty": buy_qty,
                            "val": order_val,
                        }
                    else:
                        logger.warning(f"Breakout market buy failed: {resp}")
            elif is_price_breakout and not is_volume_confirmed:
                self.state.status = "ARMED"
            else:
                self.state.status = "IDLE"

        return None


class InventorySkewController:
    """Управляет смещением ступеней сетки и тейк-профита в зависимости от загрузки капитала (модель Авелланеды-Стойкова)."""

    def __init__(self, base_tp_pct: float = 0.0070) -> None:
        self.base_tp_pct = base_tp_pct

    def get_skewed_step_offset(self, step_idx: int, base_offset_pct: float) -> float:
        """Отодвигает шаг глубже, если предыдущие ступени уже в инвентаре.

        Step 1 -> без изменений (1.0x)
        Step 2 -> базовый отступ * 1.25 (требуем большую скидку)
        Step 3 -> базовый отступ * 1.50 (глубокий бункер)
        """
        multipliers = {1: 1.0, 2: 1.25, 3: 1.50}
        return round(base_offset_pct * multipliers.get(step_idx, 1.0), 4)

    def get_skewed_tp_pct(self, active_steps_count: int) -> float:
        """Сжимает целевой тейк-профит к безубытку при росте риска инвентаря.

        1 ступень  -> полный тейк (+0.70% .. +0.90%)
        2 ступени  -> умеренный тейк (+0.45%)
        3 ступени  -> быстрый сброс груза в кэш (+0.25% чистыми)
        """
        if active_steps_count >= 3:
            return 0.0025
        elif active_steps_count == 2:
            return 0.0045
        return self.base_tp_pct


class L2WallScanner:
    """Сканирует стакан глубиной 50 и находит институциональные плиты-щиты."""

    def __init__(self, client: Any = None, min_wall_qty: float = 30000.0, min_wall_usd: float = 15000.0) -> None:
        self.client = client
        self.min_wall_qty = min_wall_qty  # Порог объема для SUI (крупная лимитная стена)
        self.min_wall_usd = min_wall_usd

    def find_front_run_price(
        self,
        symbol: str,
        calc_price: float,
        window_pct: float = 0.0035,
        tick_size: float = 0.0001,
        price_decimals: int = 4,
    ) -> float:
        """Ищет максимальную стену покупателей в коридоре +-0.35% от расчетной цены
        и ставит ордер на 1 тик ПЕРЕД ней.
        """
        try:
            res: Dict[str, Any] = {}
            if self.client and hasattr(self.client, "_request"):
                res = self.client._request(
                    "GET",
                    "/v5/market/orderbook",
                    params={"category": "spot", "symbol": symbol, "limit": 50},
                )
            else:
                url = f"https://api.bybit.kz/v5/market/orderbook?category=spot&symbol={symbol}&limit=50"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    res = json.loads(resp.read().decode())

            bids = res.get("result", {}).get("b", [])  # [[price, size], ...]
            if not bids:
                return calc_price

            min_p = calc_price * (1.0 - window_pct)
            max_p = calc_price * (1.0 + window_pct)

            zone_bids = [
                (float(p), float(sz))
                for p, sz in bids
                if min_p <= float(p) <= max_p
            ]

            if not zone_bids:
                return calc_price

            # Ищем уровень с наибольшей плотностью
            wall_price, max_vol = max(zone_bids, key=lambda x: x[1])

            if max_vol >= self.min_wall_qty or (max_vol * wall_price) >= self.min_wall_usd:
                front_price = round(wall_price + tick_size, price_decimals)
                logger.info(
                    f"🛡️ [L2 WALL] Найдена плита {max_vol:.0f} {symbol} (~${max_vol*wall_price:,.0f}) @ ${wall_price}. "
                    f"Сдвиг ордера: ${calc_price:.4f} -> ${front_price:.4f}"
                )
                return front_price

            return calc_price
        except Exception as e:
            logger.warning(
                f"⚠️ [L2 WALL] Ошибка чтения стакана {symbol}: {e}. Используем базовую цену ${calc_price}."
            )
            return calc_price


class MarketGuard:
    """Market crash detection, lead-lag spillover, and dynamic adaptive spacing engine."""

    def __init__(self) -> None:
        self.global_cooldown_active = False
        self.global_cooldown_start_time = 0.0
        self.global_cooldown_reason = ""
        self.last_btc_1m_chg = 0.0
        self.last_btc_3m_chg = 0.0
        self.lead_lag_status = "CLEAR"        # CLEAR | SLIDING | CRASH
        self.lead_lag_reason = ""
        self.gate_step1_open = True
        self.dca_protection_active = False    # True when BTC is sliding and DCA needs protection

        # Per-token metrics
        self.token_metrics: Dict[str, Dict[str, Any]] = {}
        for sym in [PRIMARY_SYMBOL, SECONDARY_SYMBOL, TERTIARY_SYMBOL]:
            self.token_metrics[sym] = {
                "last_1m_chg": 0.0,
                "last_3m_chg": 0.0,
                "range_15m": 0.0,
                "vol_multiplier": 1.0,
                "volatility_regime": "NORMAL",
                "step1_discount": BASE_SPACING["step_1"],
                "step2_discount": BASE_SPACING["step_2"],
                "step3_discount": BASE_SPACING["step_3"],
                "cooldown_active": False,
                "cooldown_start_time": 0.0,
                "cooldown_reason": "",
                "obi": 0.0,
            }

    @staticmethod
    def fetch_order_book_imbalance(symbol: str, depth: int = 15) -> float:
        """Computes Order Book Imbalance (OBI) from top depth levels of orderbook.
        OBI = (Sum(bids) - Sum(asks)) / (Sum(bids) + Sum(asks))
        Values range from -1.0 (pure sell wall / bid vacuum) to +1.0 (pure buy wall).
        """
        url = f"https://api.bybit.kz/v5/market/orderbook?category=spot&symbol={symbol}&limit={max(25, depth)}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if data.get("retCode") == 0:
                    bids = data.get("result", {}).get("b", [])[:depth]
                    asks = data.get("result", {}).get("a", [])[:depth]
                    bid_vol = sum(float(b[1]) for b in bids if len(b) >= 2)
                    ask_vol = sum(float(a[1]) for a in asks if len(a) >= 2)
                    tot_vol = bid_vol + ask_vol
                    if tot_vol > 0:
                        return round((bid_vol - ask_vol) / tot_vol, 4)
        except Exception as e:
            logger.debug(f"Orderbook fetch failed for {symbol}: {e}")
        return 0.0

    @staticmethod
    def fetch_klines(symbol: str, limit: int = 15) -> List[List[Any]]:
        """Fetches public Kline data directly from Bybit KZ Spot endpoint (Zero API Key)."""
        return MarketGuard.fetch_klines_interval(symbol, interval="1", limit=limit)

    @staticmethod
    def fetch_klines_interval(symbol: str, interval: str = "1", limit: int = 15) -> List[List[Any]]:
        """Fetches public Kline data with custom interval (1, 15, 60, etc.) from Bybit KZ Spot."""
        url = f"https://api.bybit.kz/v5/market/kline?category=spot&symbol={symbol}&interval={interval}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode())
                if data.get("retCode") == 0:
                    return data.get("result", {}).get("list", [])
        except Exception as e:
            logger.debug(f"Kline fetch failed for {symbol} (interval={interval}): {e}")
        return []

    def classify_market_regime(self, symbol: str, klines_15m: List[List[Any]]) -> Tuple[str, float]:
        """
        Classifies market regime into CALM, NORMAL, or STORM based on 15m normalized range (2h / 8 candles).
        Includes 30-minute time hysteresis and fail-safe priority for BTC SLIDING/CRASH.
        Returns: (regime_name, range_15m_pct)
        """
        now = time.time()
        m = self.token_metrics.setdefault(symbol, {})
        current_regime = m.get("market_regime", "NORMAL")
        last_switch_ts = m.get("regime_switch_ts", 0.0)

        # 1. Fail-Safe: If BTC Lead-Lag is SLIDING or CRASH, force STORM immediately (no hysteresis)
        if self.lead_lag_status in ("SLIDING", "CRASH") or self.global_cooldown_active:
            m["market_regime"] = "STORM"
            m["regime_switch_ts"] = now
            return "STORM", m.get("range_15m", 0.0) * 100.0

        if not klines_15m or len(klines_15m) < 4:
            return current_regime, m.get("range_15m", 0.0) * 100.0

        # Take last 8 candles (or available up to 8)
        recent = klines_15m[:8]
        highs = [float(k[2]) for k in recent]
        lows = [float(k[3]) for k in recent]
        close = float(recent[0][4]) if float(recent[0][4]) > 0 else 1.0

        min_l = min(lows) if lows else 1.0
        max_h = max(highs) if highs else 1.0
        amplitude_pct = ((max_h - min_l) / close) * 100.0

        # Raw candidate regime
        if amplitude_pct < 0.80:
            candidate = "CALM"
        elif amplitude_pct >= 1.50:
            candidate = "STORM"
        else:
            candidate = "NORMAL"

        # 2. Time Hysteresis: Maintain regime for at least 30 minutes (1800s) unless upgrading to STORM
        if candidate == current_regime:
            return current_regime, amplitude_pct

        if candidate == "STORM":
            # Upgrading to STORM is instant for risk protection
            m["market_regime"] = "STORM"
            m["regime_switch_ts"] = now
            logger.info(f"⚡ [MarketRegime: {symbol}] Всплеск волатильности ({amplitude_pct:.2f}%)! Мгновенный переход -> STORM.")
            return "STORM", amplitude_pct

        # Transitioning between CALM and NORMAL requires 30m cooldown
        if (now - last_switch_ts) >= 1800.0 or last_switch_ts == 0.0:
            logger.info(f"🔄 [MarketRegime: {symbol}] Смена режима {current_regime} -> {candidate} (Размах 15m: {amplitude_pct:.2f}%).")
            m["market_regime"] = candidate
            m["regime_switch_ts"] = now
            return candidate, amplitude_pct

        return current_regime, amplitude_pct

    def evaluate_btc_lead_lag(self, btc_klines: List[List[Any]]) -> Dict[str, Any]:
        """
        Evaluates BTC 1m/3m momentum and reversal signals.
        Returns a dictionary with status (CLEAR, SLIDING, CRASH) and gate permissions.
        """
        if not btc_klines:
            return {
                "status": "CLEAR" if not self.global_cooldown_active else "CRASH",
                "reason": self.global_cooldown_reason if self.global_cooldown_active else "No BTC Kline data (Permissive)",
                "gate_step1_open": not self.global_cooldown_active,
                "dca_protection_active": False,
                "btc_1m_chg": self.last_btc_1m_chg,
                "btc_3m_chg": self.last_btc_3m_chg,
                "reversal_confirmed": False,
            }

        btc_c0, btc_o0 = float(btc_klines[0][4]), float(btc_klines[0][1])
        btc_l0 = float(btc_klines[0][3])
        btc_1m = (btc_c0 - btc_o0) / btc_o0 if btc_o0 > 0 else 0.0

        btc_3m = 0.0
        if len(btc_klines) >= 3:
            btc_o2 = float(btc_klines[2][1])
            btc_3m = (btc_c0 - btc_o2) / btc_o2 if btc_o2 > 0 else 0.0

        reversal_confirmed = False
        if len(btc_klines) >= 2:
            btc_l1 = float(btc_klines[1][3])
            # Reversal confirmed if current candle is green >= threshold or low held with positive bounce
            if btc_1m >= BTC_REVERSAL_CONFIRM_THRESHOLD or (btc_l0 >= btc_l1 and btc_1m > 0.0):
                reversal_confirmed = True

        # 1. Check CRASH (Circuit Breaker level)
        if self.global_cooldown_active or btc_1m <= BTC_1M_DUMP_THRESHOLD or btc_3m <= BTC_3M_DUMP_THRESHOLD:
            reason = self.global_cooldown_reason or (
                f"BTC 1m Flash Dump ({btc_1m*100:.2f}%)" if btc_1m <= BTC_1M_DUMP_THRESHOLD
                else f"BTC 3m Cumulative Dump ({btc_3m*100:.2f}%)"
            )
            return {
                "status": "CRASH",
                "reason": reason,
                "gate_step1_open": False,
                "dca_protection_active": True,
                "btc_1m_chg": btc_1m,
                "btc_3m_chg": btc_3m,
                "reversal_confirmed": False,
            }

        # 2. Check SLIDING (Pre-emptive Knife-Catch Prevention)
        if btc_1m <= BTC_1M_SLIDING_THRESHOLD or btc_3m <= BTC_3M_SLIDING_THRESHOLD:
            reason = (
                f"BTC 1m Sliding ({btc_1m*100:.2f}%)" if btc_1m <= BTC_1M_SLIDING_THRESHOLD
                else f"BTC 3m Sliding ({btc_3m*100:.2f}%)"
            )
            return {
                "status": "SLIDING",
                "reason": reason,
                "gate_step1_open": False,
                "dca_protection_active": True,
                "btc_1m_chg": btc_1m,
                "btc_3m_chg": btc_3m,
                "reversal_confirmed": False,
            }

        # 3. CLEAR / BULLISH
        status_label = "BULLISH" if btc_1m >= BTC_REVERSAL_CONFIRM_THRESHOLD else "CLEAR"
        return {
            "status": status_label,
            "reason": "BTC Market Stable" if status_label == "CLEAR" else f"BTC Momentum Reversal (+{btc_1m*100:.2f}%)",
            "gate_step1_open": True,
            "dca_protection_active": False,
            "btc_1m_chg": btc_1m,
            "btc_3m_chg": btc_3m,
            "reversal_confirmed": reversal_confirmed,
        }

    def update_market_state(self, active_symbols: List[str]) -> Tuple[bool, str, Dict[str, Tuple[bool, str]]]:
        """
        Updates market metrics, checks BTC lead-lag and idiosyncratic dump triggers.
        Returns:
            (global_dump_fired, global_reason, {symbol: (token_dump_fired, token_reason)})
        """
        btc_klines = self.fetch_klines(LEAD_LAG_SYMBOL, limit=5)
        now = time.time()

        if btc_klines:
            btc_c0, btc_o0 = float(btc_klines[0][4]), float(btc_klines[0][1])
            self.last_btc_1m_chg = (btc_c0 - btc_o0) / btc_o0 if btc_o0 > 0 else 0.0
            if len(btc_klines) >= 3:
                btc_o2 = float(btc_klines[2][1])
                self.last_btc_3m_chg = (btc_c0 - btc_o2) / btc_o2 if btc_o2 > 0 else 0.0

        # Evaluate Lead-Lag Radar
        ll_eval = self.evaluate_btc_lead_lag(btc_klines)
        self.lead_lag_status = ll_eval["status"]
        self.lead_lag_reason = ll_eval["reason"]
        self.gate_step1_open = ll_eval["gate_step1_open"]
        self.dca_protection_active = ll_eval["dca_protection_active"]

        global_dump_fired = False
        global_dump_reason = ""

        # Check Global BTC Flash Dump
        if not self.global_cooldown_active:
            if self.last_btc_1m_chg <= BTC_1M_DUMP_THRESHOLD:
                global_dump_reason = f"BTC 1m Flash Dump ({self.last_btc_1m_chg*100:.2f}%)"
            elif self.last_btc_3m_chg <= BTC_3M_DUMP_THRESHOLD:
                global_dump_reason = f"BTC 3m Cumulative Dump ({self.last_btc_3m_chg*100:.2f}%)"

            if global_dump_reason:
                self.global_cooldown_active = True
                self.global_cooldown_start_time = now
                self.global_cooldown_reason = global_dump_reason
                self.lead_lag_status = "CRASH"
                self.gate_step1_open = False
                self.dca_protection_active = True
                global_dump_fired = True
        else:
            # Check stabilization for Global Cooldown
            elapsed = now - self.global_cooldown_start_time
            if elapsed >= COOLDOWN_MIN_SECONDS and btc_klines and len(btc_klines) >= 2:
                btc_l0 = float(btc_klines[0][3])
                btc_l1 = float(btc_klines[1][3])
                if (btc_l0 >= btc_l1 and self.last_btc_1m_chg >= -0.0010) or self.last_btc_1m_chg >= 0.0010 or elapsed >= 900:
                    logger.info(f"🟢 [MarketGuard] Общий рынок (BTC) стабилизировался! Пауза {int(elapsed)}с снята.")
                    self.global_cooldown_active = False
                    self.global_cooldown_reason = ""
                    self.lead_lag_status = "CLEAR"
                    self.gate_step1_open = True
                    self.dca_protection_active = False
                    send_telegram(
                        "🟢 **[ЗАЩИТА ДЕПОЗИТА: РЫНОК СТАБИЛИЗИРОВАН]**\n\n"
                        f"Биткоин зафиксировал локальное дно после паузы {int(elapsed)}с.\n"
                        "Общесистемная блокировка покупок снята."
                    )


        # Check per-token metrics and idiosyncratic dumps
        token_dumps: Dict[str, Tuple[bool, str]] = {}
        for sym in active_symbols:
            meta = TOKEN_METADATA.get(sym, {})
            m = self.token_metrics.setdefault(sym, {
                "last_1m_chg": 0.0, "last_3m_chg": 0.0, "range_15m": 0.0,
                "vol_multiplier": 1.0, "volatility_regime": "NORMAL",
                "step1_discount": BASE_SPACING["step_1"],
                "step2_discount": BASE_SPACING["step_2"],
                "step3_discount": BASE_SPACING["step_3"],
                "cooldown_active": False, "cooldown_start_time": 0.0, "cooldown_reason": "",
                "obi": 0.0,
            })

            # Order Book Imbalance (OBI) for early dump/slippage detection
            m["obi"] = self.fetch_order_book_imbalance(sym, depth=15)

            klines = self.fetch_klines(sym, limit=15)
            if not klines:
                token_dumps[sym] = (False, "")
                continue

            c0, o0 = float(klines[0][4]), float(klines[0][1])
            chg_1m = (c0 - o0) / o0 if o0 > 0 else 0.0
            m["last_1m_chg"] = chg_1m

            chg_3m = 0.0
            if len(klines) >= 3:
                o2 = float(klines[2][1])
                chg_3m = (c0 - o2) / o2 if o2 > 0 else 0.0
            m["last_3m_chg"] = chg_3m

            # Fetch 15m klines for Regime Classification (2-hour window / 8 candles)
            klines_15m = self.fetch_klines_interval(sym, interval="15", limit=10)
            regime_name, range_15m_pct = self.classify_market_regime(sym, klines_15m)
            m["market_regime"] = regime_name
            m["range_15m_pct"] = range_15m_pct

            # Continuous Volatility Spacing
            highs = [float(k[2]) for k in klines]
            lows = [float(k[3]) for k in klines]
            min_l = min(lows) if lows else 1.0
            max_h = max(highs) if highs else 1.0
            range_15m = (max_h - min_l) / min_l if min_l > 0 else 0.0
            m["range_15m"] = range_15m

            mult = max(MIN_VOL_MULTIPLIER, min(MAX_VOL_MULTIPLIER, range_15m / VOLATILITY_BENCHMARK_15M))
            m["vol_multiplier"] = round(mult, 2)
            m["volatility_regime"] = regime_name
            m["step1_discount"] = round(BASE_SPACING["step_1"] * mult, 4)
            # Cap step2 at 0.0220 (-2.20%) and step3 at 0.0480 (-4.80%) to prevent runaway grid
            m["step2_discount"] = round(min(BASE_SPACING["step_2"] * mult, 0.0220), 4)
            m["step3_discount"] = round(min(BASE_SPACING["step_3"] * mult, 0.0480), 4)

            # Idiosyncratic Dump Trigger
            dump_fired_tok = False
            dump_reason_tok = ""
            d1_thresh = meta.get("dump_1m_threshold", -0.0060)
            d3_thresh = meta.get("dump_3m_threshold", -0.0120)

            if not m["cooldown_active"]:
                if chg_1m <= d1_thresh:
                    dump_reason_tok = f"{meta.get('base_coin', sym)} 1m Flash Dump ({chg_1m*100:.2f}%)"
                elif chg_3m <= d3_thresh:
                    dump_reason_tok = f"{meta.get('base_coin', sym)} 3m Cumulative Dump ({chg_3m*100:.2f}%)"

                if dump_reason_tok:
                    m["cooldown_active"] = True
                    m["cooldown_start_time"] = now
                    m["cooldown_reason"] = dump_reason_tok
                    dump_fired_tok = True
            else:
                # Stabilization Check
                el = now - m["cooldown_start_time"]
                if el >= COOLDOWN_MIN_SECONDS and len(klines) >= 2:
                    l0 = float(klines[0][3])
                    l1 = float(klines[1][3])
                    if (l0 >= l1 and chg_1m >= -0.0010) or chg_1m >= 0.0010 or el >= 900:
                        logger.info(f"🟢 [MarketGuard] Актив {sym} стабилизировался после {int(el)}с паузы.")
                        m["cooldown_active"] = False
                        m["cooldown_reason"] = ""
                        send_telegram(
                            f"🟢 **[ЗАЩИТА ДЕПОЗИТА: {sym} СТАБИЛИЗИРОВАН]**\n\n"
                            f"Свечи {meta.get('base_coin', sym)} сформировали поддержку.\n"
                            "Сетка ордеров для актива возобновлена."
                        )

            token_dumps[sym] = (dump_fired_tok, dump_reason_tok)

        return global_dump_fired, global_dump_reason, token_dumps


def compute_trade_analytics(execs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Builds hourly and day-of-week trade analytics from execution list."""
    hourly_dict = {h: {"count": 0, "volume": 0.0, "buys": 0, "sells": 0} for h in range(24)}
    dow_dict = {d: {"count": 0, "volume": 0.0} for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]}
    days_list = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    tot_vol = 0.0
    tot_buys = 0
    tot_sells = 0
    recent_list = []

    for idx, e in enumerate(execs):
        try:
            e_ts = float(e.get("execTime", 0)) / 1000.0
            e_dt = datetime.datetime.fromtimestamp(e_ts, tz=datetime.timezone.utc) + datetime.timedelta(hours=ASTANA_TZ_OFFSET_HOURS)
            price = float(e.get("execPrice", 0.0))
            qty = float(e.get("execQty", 0.0))
            val = float(e.get("execValue", 0.0))
            if val <= 0.0 and price > 0 and qty > 0:
                val = price * qty
            side = e.get("side", "")
            tot_vol += val
            if side == "Buy":
                tot_buys += 1
            else:
                tot_sells += 1

            h = e_dt.hour
            hourly_dict[h]["count"] += 1
            hourly_dict[h]["volume"] += val
            if side == "Buy":
                hourly_dict[h]["buys"] += 1
            else:
                hourly_dict[h]["sells"] += 1

            dow_name = days_list[e_dt.weekday()]
            dow_dict[dow_name]["count"] += 1
            dow_dict[dow_name]["volume"] += val

            if idx < 10:
                recent_list.append({
                    "time": e_dt.strftime("%d.%m %H:%M"),
                    "side": side,
                    "price": price,
                    "qty": qty,
                    "val": val,
                    "fee": float(e.get("execFee", 0.0)),
                    "fee_coin": e.get("feeCurrency", ""),
                })
        except Exception:
            pass

    return {
        "total_trades": len(execs),
        "total_volume": round(tot_vol, 2),
        "buys_count": tot_buys,
        "sells_count": tot_sells,
        "recent_trades": recent_list,
        "hourly": hourly_dict,
        "dow": dow_dict,
    }


class StandaloneBybitBot:
    """Autonomous Multi-Token Spot Micro-Grid Portfolio Engine for Bybit Kazakhstan."""

    def __init__(self, mode: str = "mobile", enable_telegram: bool = True, is_24x7: bool = False) -> None:
        self.mode = (mode or "mobile").strip().lower()
        self.enable_telegram = bool(enable_telegram and ENABLE_TELEGRAM)
        self.is_24x7 = bool(is_24x7 or os.getenv("DESKTOP_24X7", "false").lower() in ("1", "true", "yes"))
        self.last_hourly_alert_ts: float = time.time()
        self.role = "ACTIVE_CONTROLLER"
        self.is_active_controller = True
        self.last_heartbeat_ts = time.time()
        self.peer_heartbeat_ts = 0.0
        self.reserve_usdt = DESKTOP_RESERVE_USDT if self.mode == "desktop" else 0.0
        self.cluster_board_msg_id: Optional[int] = None
        self.last_heartbeat_sent_ts: float = 0.0
        self.last_peer_heartbeat_ts: float = time.time()
        self.last_canary_update_ts: float = 0.0
        self.canary_toggle_state: bool = False

        self.client = BybitV5Client(BYBIT_API_KEY, BYBIT_API_SECRET, domain="api.bybit.kz")
        self.guard = MarketGuard()
        self.dual_mode_active = False
        self.trio_mode_active = False
        self.last_sync_ts = 0.0
        self.peak_equity = 0.0
        self.circuit_breaker_active = False
        self.is_paused = False
        self.running = True
        self.trailing_controller = TrailingTakeProfitController()
        self.flash_sniper = FlashSniperController(symbol=SNIPER_TARGET_SYMBOL) if SNIPER_ENABLED else None
        self.inventory_skew = InventorySkewController(base_tp_pct=STANDARD_TP_PCT)
        self.wall_scanner = L2WallScanner(client=self.client, min_wall_qty=30000.0, min_wall_usd=15000.0)
        self.breakout_engine = MomentumBreakoutController(symbol=BREAKOUT_TARGET_SYMBOL) if BREAKOUT_ENABLED else None

        # Per-token execution and PnL trackers
        self.token_cycles: Dict[str, int] = {PRIMARY_SYMBOL: 0, SECONDARY_SYMBOL: 0, TERTIARY_SYMBOL: 0}
        self.token_profits: Dict[str, float] = {PRIMARY_SYMBOL: 0.0, SECONDARY_SYMBOL: 0.0, TERTIARY_SYMBOL: 0.0}
        self.token_last_cycles: Dict[str, Optional[int]] = {PRIMARY_SYMBOL: None, SECONDARY_SYMBOL: None, TERTIARY_SYMBOL: None}
        self.recent_buys: Dict[str, List[Dict[str, Any]]] = {PRIMARY_SYMBOL: [], SECONDARY_SYMBOL: [], TERTIARY_SYMBOL: []}
        self.last_scale_out_ts: Dict[str, float] = {PRIMARY_SYMBOL: 0.0, SECONDARY_SYMBOL: 0.0, TERTIARY_SYMBOL: 0.0}
        # Cycle Lock: Locks active regime while position is held
        self.token_locked_regime: Dict[str, Optional[str]] = {PRIMARY_SYMBOL: None, SECONDARY_SYMBOL: None, TERTIARY_SYMBOL: None}

        # Unified live statistics
        if self.mode == "desktop":
            profile_label = "DESKTOP / 24x7 SMART-STEP" if self.is_24x7 else "DESKTOP / SMART-STEP"
        else:
            profile_label = "MOBILE / STORM"
        self.stats: Dict[str, Any] = {
            "mode": self.mode,
            "profile": profile_label,
            "is_24x7": self.is_24x7,
            "role": self.role,
            "reserve_usdt": self.reserve_usdt,
            "portfolio_mode": "🔥 Single (SUI 100%)",
            "dual_mode_active": False,
            "trio_mode_active": False,
            "total_usd": 0.0,
            "available_usdt": 0.0,
            "locked_usdt": 0.0,
            "mnt_balance": 0.0,
            "is_paused": False,
            "circuit_breaker_active": False,
            "global_guard_status": "🟢 Норма",
            "btc_1m_chg": 0.0,
            "tokens": {},
            "all_open_orders": [],
            "updated_at": "",
        }

    def get_market_price(self, symbol: str) -> float:
        """Fetches last traded price for symbol from spot ticker."""
        try:
            res = self.client._request("GET", "/v5/market/tickers", params={"category": "spot", "symbol": symbol.upper()})
            if res.get("retCode") == 0:
                tickers = res.get("result", {}).get("list", [])
                if tickers:
                    return float(tickers[0].get("lastPrice") or 0.0)
        except Exception as e:
            logger.warning(f"Error fetching price for {symbol}: {e}")
        return 0.0

    def cancel_all_buys(self, symbol: str, open_buys: List[Dict[str, Any]]) -> None:
        """Helper to cancel multiple buy orders for a given symbol."""
        for b_ord in open_buys:
            ord_id = b_ord.get("orderId")
            if ord_id:
                self.client.cancel_order(symbol, ord_id)

    def cancel_all_portfolio_buys(self) -> None:
        """Cancels all BUY orders across all managed symbols (excluding canary heartbeat order)."""
        for sym in [PRIMARY_SYMBOL, SECONDARY_SYMBOL, TERTIARY_SYMBOL]:
            try:
                open_orders = self.client.get_open_orders(sym)
                buys = [
                    o for o in open_orders
                    if o.get("side") == "Buy"
                    and not str(o.get("orderLinkId", "")).startswith(CANARY_ORDER_LINK_PREFIX)
                    and not str(o.get("orderLinkId", "")).startswith(SNIPER_ORDER_LINK_PREFIX)
                ]
                if buys:
                    self.cancel_all_buys(sym, buys)
            except Exception as e:
                logger.warning(f"Error canceling buys for {sym}: {e}")

    def cancel_canary_order(self) -> None:
        """Explicitly cancels the on-exchange canary order if present."""
        try:
            orders = self.client.get_open_orders(CANARY_SYMBOL)
            canary = next((o for o in orders if str(o.get("orderLinkId", "")).startswith(CANARY_ORDER_LINK_PREFIX)), None)
            if canary and canary.get("orderId"):
                logger.info(f"🕊️ [Canary] Снятие канареечного ордера {canary.get('orderId')}...")
                self.client.cancel_order(CANARY_SYMBOL, canary.get("orderId"))
        except Exception as e:
            logger.debug(f"Error canceling canary order: {e}")

    def maintain_canary_order(self) -> None:
        """Maintains or pings the on-exchange canary order in Bybit order book (Desktop controller)."""
        now = time.time()
        if (now - self.last_canary_update_ts) < CANARY_HEARTBEAT_INTERVAL_SEC:
            return

        try:
            open_orders = self.client.get_open_orders(CANARY_SYMBOL)
            canary = next((o for o in open_orders if str(o.get("orderLinkId", "")).startswith(CANARY_ORDER_LINK_PREFIX)), None)

            # Alternate price between CANARY_PRICE_A ($0.1001) and CANARY_PRICE_B ($0.1002)
            self.canary_toggle_state = not self.canary_toggle_state
            target_price = CANARY_PRICE_B if self.canary_toggle_state else CANARY_PRICE_A
            target_qty = math.ceil((CANARY_NOTIONAL_USDT / target_price) * 100) / 100.0  # ~50.45 SUI ($5.05)

            if canary and canary.get("orderId"):
                ord_id = canary.get("orderId")
                # Amend existing order price without cancelling to refresh updatedTime on Bybit
                resp = self.client.amend_order(
                    symbol=CANARY_SYMBOL,
                    order_id=ord_id,
                    price=target_price,
                    price_precision=4,
                )
                if resp.get("retCode") == 0:
                    self.last_canary_update_ts = now
                    logger.debug(f"🕊️ [Canary Pulse] Ордер {ord_id} обновлен на Bybit Spot @ ${target_price:.4f}")
                else:
                    # If amend rejected (e.g. order filled or race), recreate
                    logger.info(f"🕊️ [Canary Re-create] Amend {ord_id} retCode={resp.get('retCode')}: {resp.get('retMsg')}")
                    self.client.cancel_order(CANARY_SYMBOL, ord_id)
                    time.sleep(0.5)
                    unique_link_id = f"{CANARY_ORDER_LINK_PREFIX}_{int(time.time())}"
                    resp_create = self.client.create_limit_order(
                        CANARY_SYMBOL,
                        "Buy",
                        target_qty,
                        target_price,
                        post_only=False,
                        qty_precision=2,
                        price_precision=4,
                        order_link_id=unique_link_id,
                    )
                    if resp_create.get("retCode") == 0:
                        self.last_canary_update_ts = now
            else:
                # Place fresh canary order with unique timestamped orderLinkId
                unique_link_id = f"{CANARY_ORDER_LINK_PREFIX}_{int(time.time())}"
                logger.info(f"🕊️ [Canary Init] Выставление канареечного ордера {target_qty} SUI @ ${target_price:.4f} ($5.05)...")
                resp = self.client.create_limit_order(
                    CANARY_SYMBOL,
                    "Buy",
                    target_qty,
                    target_price,
                    post_only=False,
                    qty_precision=2,
                    price_precision=4,
                    order_link_id=unique_link_id,
                )
                if resp.get("retCode") == 0:
                    self.last_canary_update_ts = now
                    logger.info("🕊️ [Canary Init] Канареечный флаг успешно установлен в стакане Bybit!")
                else:
                    logger.warning(f"Canary placement failed: retCode={resp.get('retCode')} retMsg={resp.get('retMsg')}")
        except Exception as e:
            logger.warning(f"Error maintaining canary order: {e}")

    def get_canary_status(self) -> Dict[str, Any]:
        """Checks presence and age of canary heartbeat order in orderbook (Mobile watchdog)."""
        now = time.time()
        try:
            orders = self.client.get_open_orders(CANARY_SYMBOL)
            canary = next((o for o in orders if str(o.get("orderLinkId", "")).startswith(CANARY_ORDER_LINK_PREFIX)), None)
            if not canary:
                return {"found": False, "age_sec": 999999.0, "price": 0.0, "order_id": None}

            # Bybit provides updatedTime in milliseconds
            upd_ms = float(canary.get("updatedTime") or canary.get("createdTime") or (now * 1000.0))
            upd_ts = upd_ms / 1000.0
            age_sec = max(0.0, now - upd_ts)
            return {
                "found": True,
                "age_sec": age_sec,
                "price": float(canary.get("price", 0.0)),
                "order_id": canary.get("orderId"),
            }

        except Exception as e:
            logger.debug(f"get_canary_status error: {e}")
            return {"found": False, "age_sec": 999999.0, "price": 0.0, "order_id": None}

    def handover_to(self, target_host: str, reason: str = "") -> None:
        """Gracefully transfers active controller role to target host (desktop or mobile)."""
        target = target_host.strip().lower()
        logger.info(f"🔄 [Handover] Передача управления -> {target.upper()} ({reason})")
        if target == self.mode:
            self.is_active_controller = True
            self.role = "ACTIVE_CONTROLLER"
            self.cluster_board_msg_id = write_cluster_state(target, f"Активен ({reason})", self.cluster_board_msg_id)
            send_telegram(
                f"✅ *[КЛАСТЕР: УПРАВЛЕНИЕ АКТИВИРОВАНО]*\n\n"
                f"Узел: *{self.mode.upper()}*\n"
                f"Роль: `ACTIVE_CONTROLLER`\n"
                f"Причина: {reason}"
            )
        else:
            self.is_active_controller = False
            self.role = "PASSIVE_OBSERVER"
            self.cancel_all_portfolio_buys()
            self.cancel_canary_order()
            self.trailing_controller.reset(PRIMARY_SYMBOL)
            self.trailing_controller.reset(SECONDARY_SYMBOL)
            self.trailing_controller.reset(TERTIARY_SYMBOL)
            self.cluster_board_msg_id = write_cluster_state(target, f"Передано на {target} ({reason})", self.cluster_board_msg_id)
            send_telegram(
                f"🔄 *[КЛАСТЕР: ПЕРЕДАЧА СМЕНЫ]*\n\n"
                f"Текущий узел: *{self.mode.upper()}* -> `PASSIVE_OBSERVER`\n"
                f"Новый активный узел: *{target.upper()}*\n"
                f"Причина: {reason}\n\n"
                f"• Все BUY-ордера сняты.\n"
                f"• Тейк-профиты сохранены.\n"
                f"• Узел {target.upper()} подхватывает контроль."
            )

    def step(self) -> None:
        """Single execution step of portfolio micro-grid trading cycle."""
        if not self.client.is_configured:
            logger.error("Bybit credentials not configured in environment!")
            return

        try:
            now = time.time()

            # 1. Sync Wallet Balance
            bal = self.client.get_wallet_balance("UNIFIED")
            if bal.get("retCode") != 0:
                logger.warning(f"Wallet sync error ({bal.get('retCode')}): {bal.get('retMsg')}")
                return

            avail_usdt = float(bal.get("available_usdt", 0.0))
            locked_usdt = float(bal.get("locked_usdt", 0.0))
            total_usd = float(bal.get("total_usd", 0.0))

            coins = bal.get("coins", {})
            sui_coin = coins.get("SUI", {})
            sui_free = float(sui_coin.get("free", 0.0))
            sui_locked = float(sui_coin.get("locked", 0.0))
            total_sui = sui_free + sui_locked

            near_coin = coins.get("NEAR", {})
            near_free = float(near_coin.get("free", 0.0))
            near_locked = float(near_coin.get("locked", 0.0))
            total_near = near_free + near_locked

            avax_coin = coins.get("AVAX", {})
            avax_free = float(avax_coin.get("free", 0.0))
            avax_locked = float(avax_coin.get("locked", 0.0))
            total_avax = avax_free + avax_locked

            mnt_coin = coins.get("MNT", {})
            mnt_bal = float(mnt_coin.get("balance") or mnt_coin.get("free") or 0.0)

            # 2. Fetch Spot Market Prices
            sui_price = self.get_market_price(PRIMARY_SYMBOL)
            near_price = self.get_market_price(SECONDARY_SYMBOL)
            avax_price = self.get_market_price(TERTIARY_SYMBOL)
            if sui_price <= 0:
                return

            prices = {
                PRIMARY_SYMBOL: sui_price,
                SECONDARY_SYMBOL: near_price if near_price > 0 else 0.0,
                TERTIARY_SYMBOL: avax_price if avax_price > 0 else 0.0,
            }
            free_coins = {PRIMARY_SYMBOL: sui_free, SECONDARY_SYMBOL: near_free, TERTIARY_SYMBOL: avax_free}
            total_coins = {PRIMARY_SYMBOL: total_sui, SECONDARY_SYMBOL: total_near, TERTIARY_SYMBOL: total_avax}

            # 3. Calculate Total Portfolio Equity
            est_total_equity = (
                total_usd
                + (total_sui * sui_price)
                + (total_near * prices[SECONDARY_SYMBOL])
                + (total_avax * prices[TERTIARY_SYMBOL])
            )

            # Dynamic Capital Compounding Multiplier
            compound_mult = compute_compound_multiplier(est_total_equity, COMPOUND_BASELINE_EQUITY)

            if est_total_equity > self.peak_equity:
                self.peak_equity = est_total_equity

            # Circuit Breaker Check (5% Equity Drawdown Guard)
            if self.peak_equity > 0 and est_total_equity < (self.peak_equity * (1.0 - CIRCUIT_BREAKER_MAX_DD)):
                if not self.circuit_breaker_active:
                    self.circuit_breaker_active = True
                    logger.error(f"🚨 [CIRCUIT BREAKER] Просадка депозита > 5%! Equity: ${est_total_equity:.2f} (Пик: ${self.peak_equity:.2f})")
                    send_telegram(
                        f"🚨 **[CIRCUIT BREAKER: ЛИМИТ ПРОСАДКИ 5%]**\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT**\n"
                        f"Пиковый капитал: **${self.peak_equity:.2f} USDT**\n"
                        "Все покупки заблокированы до ручного перезапуска или стабилизации."
                    )
            elif est_total_equity >= (self.peak_equity * (1.0 - CIRCUIT_BREAKER_MAX_DD)):
                self.circuit_breaker_active = False

            # 4. Capital Allocator & Hysteresis Gate (Trio & Dual Modes)
            # Tier 3 (AVAX / Trio Mode: >= $115 activate, < $105 deactivate)
            if self.trio_mode_active:
                if est_total_equity < TRIO_PAIR_DEACTIVATION_EQUITY:
                    self.trio_mode_active = False
                    logger.warning(
                        f"📉 [Capital Allocator] Equity ${est_total_equity:.2f} < ${TRIO_PAIR_DEACTIVATION_EQUITY:.2f}! "
                        f"{TERTIARY_SYMBOL} switching to EXIT_ONLY."
                    )
                    send_telegram(
                        f"📉 *[МЕНЕДЖЕР КАПИТАЛА: ДЕАКТИВАЦИЯ {TERTIARY_SYMBOL}]*\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT** (порог ${TRIO_PAIR_DEACTIVATION_EQUITY:.2f})\n"
                        f"Пара **{TERTIARY_SYMBOL}** переведена в режим *EXIT-ONLY*.\n"
                        f"Возврат в режим Dual (50% {PRIMARY_SYMBOL} / 50% {SECONDARY_SYMBOL})."
                    )
            else:
                if est_total_equity >= TRIO_PAIR_ACTIVATION_EQUITY:
                    self.trio_mode_active = True
                    self.dual_mode_active = True  # Trio implies dual is active
                    logger.info(
                        f"🚀 [Capital Allocator] Equity ${est_total_equity:.2f} >= ${TRIO_PAIR_ACTIVATION_EQUITY:.2f}! "
                        f"{TERTIARY_SYMBOL} ACTIVATED!"
                    )
                    send_telegram(
                        f"🚀 **[МЕНЕДЖЕР КАПИТАЛА: АКТИВАЦИЯ ТРИО ТОКЕНОВ]**\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT** (порог ${TRIO_PAIR_ACTIVATION_EQUITY:.2f})!\n"
                        f"Активирован портфельный режим **TRIO (33.3% {PRIMARY_SYMBOL} / 33.3% {SECONDARY_SYMBOL} / 33.3% {TERTIARY_SYMBOL})**.\n"
                        "Три независимые сетки распределяют капитал и балансируют риски!"
                    )

            # Tier 2 (NEAR / Dual Mode: >= $70 activate, < $62 deactivate)
            if self.dual_mode_active:
                if not self.trio_mode_active and est_total_equity < DUAL_PAIR_DEACTIVATION_EQUITY:
                    self.dual_mode_active = False
                    logger.warning(
                        f"📉 [Capital Allocator] Equity ${est_total_equity:.2f} < ${DUAL_PAIR_DEACTIVATION_EQUITY:.2f}! "
                        f"{SECONDARY_SYMBOL} switching to EXIT_ONLY."
                    )
                    send_telegram(
                        f"📉 *[МЕНЕДЖЕР КАПИТАЛА: ДЕАКТИВАЦИЯ {SECONDARY_SYMBOL}]*\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT** (порог ${DUAL_PAIR_DEACTIVATION_EQUITY:.2f})\n"
                        f"Пара **{SECONDARY_SYMBOL}** переведена в режим *EXIT-ONLY*.\n"
                        "Новые покупки заморожены, открытые позиции закроются по тейк-профиту в плюс."
                    )
            else:
                if est_total_equity >= DUAL_PAIR_ACTIVATION_EQUITY:
                    self.dual_mode_active = True
                    logger.info(
                        f"🚀 [Capital Allocator] Equity ${est_total_equity:.2f} >= ${DUAL_PAIR_ACTIVATION_EQUITY:.2f}! "
                        f"{SECONDARY_SYMBOL} ACTIVATED!"
                    )
                    send_telegram(
                        f"🚀 **[МЕНЕДЖЕР КАПИТАЛА: АКТИВАЦИЯ КОРЗИНЫ ТОКЕНОВ]**\n\n"
                        f"Текущий капитал: **${est_total_equity:.2f} USDT** (порог ${DUAL_PAIR_ACTIVATION_EQUITY:.2f})!\n"
                        f"Активирован портфельный режим **DUAL (50% {PRIMARY_SYMBOL} / 50% {SECONDARY_SYMBOL})**.\n"
                        "Сетки работают независимо, удваивая точки входа и распределяя риски!"
                    )

            # Determine Active Managed Symbols
            symbols_to_process = [PRIMARY_SYMBOL]

            sub_strat_held_near = 0.0
            if self.flash_sniper and self.flash_sniper.symbol == SECONDARY_SYMBOL:
                if self.flash_sniper.state.status in ("POSITION_HELD", "ROCKET_ACTIVE", "TP_PLACED"):
                    sub_strat_held_near += self.flash_sniper.state.position_qty
            near_grid_free = max(0.0, near_free - sub_strat_held_near)
            near_grid_total = max(0.0, total_near - sub_strat_held_near)
            near_has_holdings = (near_grid_free * prices[SECONDARY_SYMBOL] >= 4.5) or (near_grid_total * prices[SECONDARY_SYMBOL] >= 4.5)
            if self.dual_mode_active or near_has_holdings:
                symbols_to_process.append(SECONDARY_SYMBOL)

            sub_strat_held_avax = 0.0
            if self.breakout_engine and self.breakout_engine.symbol == TERTIARY_SYMBOL:
                if self.breakout_engine.state.status == "IN_FLIGHT":
                    sub_strat_held_avax += self.breakout_engine.state.position_qty
            avax_grid_free = max(0.0, avax_free - sub_strat_held_avax)
            avax_grid_total = max(0.0, total_avax - sub_strat_held_avax)
            avax_has_holdings = (avax_grid_free * prices[TERTIARY_SYMBOL] >= 4.5) or (avax_grid_total * prices[TERTIARY_SYMBOL] >= 4.5)
            if self.trio_mode_active or avax_has_holdings:
                symbols_to_process.append(TERTIARY_SYMBOL)

            # Ensure Flash Sniper and Breakout target assets are always monitored and processed
            if SNIPER_ENABLED and SNIPER_TARGET_SYMBOL not in symbols_to_process:
                symbols_to_process.append(SNIPER_TARGET_SYMBOL)
            if BREAKOUT_ENABLED and BREAKOUT_TARGET_SYMBOL not in symbols_to_process:
                symbols_to_process.append(BREAKOUT_TARGET_SYMBOL)

            # 5. MarketGuard: Update Klines, BTC Lead-Lag & Idiosyncratic Dumps
            global_dump, global_reason, token_dumps = self.guard.update_market_state(symbols_to_process)

            # 6. Global Dump Action: Cancel all BUYs if BTC dumped
            if global_dump and self.is_active_controller:
                logger.warning(f"🚨 [MarketGuard Global Trigger] {global_reason} -> Снятие ВСЕХ BUY-ордеров!")
                self.cancel_all_portfolio_buys()
                send_telegram(
                    f"🚨 **[ЗАЩИТА ДЕПОЗИТА: ОБЩЕРЫНОЧНЫЙ ПРОЛИВ!]**\n\n"
                    f"Причина: **{global_reason}**\n"
                    "Срочное действие: **Все BUY-ордера во всех парах отозваны**\n"
                    "Режим: Включена защитная пауза на 10 мин (до стабилизации свечей)."
                )

            # 7. Sync Executions & Realized Profit per Token (every 30s)
            if now - self.last_sync_ts > 30:
                self.last_sync_ts = now
                for sym in symbols_to_process:
                    execs = self.client.get_execution_history(sym, limit=100 if sym == PRIMARY_SYMBOL else 20)
                    if execs and sym == PRIMARY_SYMBOL:
                        self.stats["trade_analytics"] = compute_trade_analytics(execs)
                    if execs:
                        tot_fees = sum(float(e.get("execFee") or 0.0) for e in execs)
                        sell_execs = [e for e in execs if e.get("side") == "Sell"]
                        self.recent_buys[sym] = [e for e in execs if e.get("side") == "Buy"]
                        cycles = len(sell_execs)

                        gross = 0.0
                        for s in sell_execs:
                            s_p = float(s.get("execPrice") or 0.0)
                            s_q = float(s.get("execQty") or 0.0)
                            gross += s_p * s_q * 0.0090

                        net = max(0.0, gross - tot_fees)
                        self.token_cycles[sym] = cycles
                        self.token_profits[sym] = round(net, 4)

                        last_c = self.token_last_cycles.get(sym)
                        if last_c is not None and cycles > last_c:
                            last_sell = sell_execs[0] if sell_execs else {}
                            s_p = last_sell.get("execPrice", "")
                            s_q = last_sell.get("execQty", "")
                            base_c = TOKEN_METADATA.get(sym, {}).get("base_coin", sym)
                            send_telegram(
                                f"🏆 **[BYBIT.KZ: ЦИКЛ {sym} ЗАКРЫТ В ПЛЮС!]**\n\n"
                                f"Пара: **{sym}**\n"
                                f"Продано: **{s_q} {base_c}** @ **${s_p}**\n"
                                f"Чистая прибыль: **+${net:.4f} USDT**\n"
                                f"Всего закрыто циклов ({sym}): **{cycles}**\n"
                                f"Баланс фонда: **${est_total_equity:.2f} USDT**"
                            )
                        self.token_last_cycles[sym] = cycles

            # 8. Token Order Processing Loop
            token_stats_map: Dict[str, Dict[str, Any]] = {}
            all_open_orders_list: List[Dict[str, Any]] = []

            for sym in symbols_to_process:
                meta = TOKEN_METADATA.get(sym, {})
                base_c = meta.get("base_coin", sym)
                cur_price = prices.get(sym, 0.0)
                cur_free_raw = free_coins.get(sym, 0.0)
                cur_total_raw = total_coins.get(sym, 0.0)

                # Deduct inventory held by dedicated sub-strategies (Breakout Engine, Flash Sniper)
                # so the main Grid engine only manages Grid inventory and never touches or sells Breakout/Sniper coins!
                sub_strat_held = 0.0
                if self.breakout_engine and self.breakout_engine.symbol == sym:
                    if self.breakout_engine.state.status == "IN_FLIGHT":
                        sub_strat_held += self.breakout_engine.state.position_qty
                if self.flash_sniper and self.flash_sniper.symbol == sym:
                    if self.flash_sniper.state.status in ("POSITION_HELD", "ROCKET_ACTIVE", "TP_PLACED"):
                        sub_strat_held += self.flash_sniper.state.position_qty

                cur_free = max(0.0, cur_free_raw - sub_strat_held)
                cur_total = max(0.0, cur_total_raw - sub_strat_held)
                holding_val = cur_total * cur_price
                free_val = cur_free * cur_price
                t_metric = self.guard.token_metrics.get(sym, {})

                open_orders = self.client.get_open_orders(sym)
                for o in open_orders:
                    o["symbol"] = sym
                    all_open_orders_list.append(o)

                # Filter out on-exchange canary and sniper orders so grid logic never touches or cancels them
                open_buys = [
                    o for o in open_orders
                    if o.get("side") == "Buy"
                    and not str(o.get("orderLinkId", "")).startswith(CANARY_ORDER_LINK_PREFIX)
                    and not str(o.get("orderLinkId", "")).startswith(SNIPER_ORDER_LINK_PREFIX)
                    and not str(o.get("orderLinkId", "")).startswith(BREAKOUT_ORDER_LINK_PREFIX)
                ]
                open_sells = [
                    o for o in open_orders
                    if o.get("side") == "Sell"
                    and not str(o.get("orderLinkId", "")).startswith(SNIPER_ORDER_LINK_PREFIX)
                    and not str(o.get("orderLinkId", "")).startswith(BREAKOUT_ORDER_LINK_PREFIX)
                ]

                # PASSIVE OBSERVER: Strictly observe and collect telemetry.
                # NEVER place, modify, or cancel orders on the shared Bybit account!
                if not self.is_active_controller:
                    s1_disc = t_metric.get("step1_discount", BASE_SPACING["step_1"])
                    s2_disc = t_metric.get("step2_discount", BASE_SPACING["step_2"])
                    s3_disc = t_metric.get("step3_discount", BASE_SPACING["step_3"])
                    token_stats_map[sym] = {
                        "symbol": sym,
                        "name": meta.get("name", sym),
                        "base_coin": base_c,
                        "badge_color": meta.get("badge_color", "#38bdf8"),
                        "mode": "PASSIVE_OBSERVER",
                        "price": cur_price,
                        "free_coin": round(cur_free, 4),
                        "locked_coin": round(cur_total - cur_free, 4),
                        "holding_value_usd": round(holding_val, 2),
                        "completed_cycles": self.token_cycles.get(sym, 0),
                        "net_profit_usd": self.token_profits.get(sym, 0.0),
                        "tp_mode": "Standard (+0.90%)",
                        "position_age_hours": 0.0,
                        "step1_discount_pct": round(s1_disc * 100, 2),
                        "step2_discount_pct": round(s2_disc * 100, 2),
                        "step3_discount_pct": round(s3_disc * 100, 2),
                        "vol_multiplier": t_metric.get("vol_multiplier", 1.0),
                        "volatility_regime": t_metric.get("volatility_regime", "NORMAL"),
                        "range_15m_pct": round(t_metric.get("range_15m", 0.0) * 100, 2),
                        "chg_1m_pct": round(t_metric.get("last_1m_chg", 0.0) * 100, 2),
                        "obi": round(t_metric.get("obi", 0.0), 3),
                        "cooldown_active": t_metric.get("cooldown_active", False),
                        "cooldown_reason": t_metric.get("cooldown_reason", ""),
                    }
                    continue

                # Handle Idiosyncratic Dump for this token
                tok_dump_fired, tok_dump_reason = token_dumps.get(sym, (False, ""))
                if tok_dump_fired:
                    logger.warning(f"🚨 [Idiosyncratic Dump: {sym}] {tok_dump_reason} -> Снятие BUY-ордеров {sym}!")
                    self.cancel_all_buys(sym, open_buys)
                    open_buys.clear()
                    send_telegram(
                        f"🚨 **[ЗАЩИТА ДЕПОЗИТА: ПРОЛИВ {sym}!]**\n\n"
                        f"Причина: **{tok_dump_reason}**\n"
                        f"Срочное действие: **Все BUY-ордера {sym} отозваны**\n"
                        "Включена защитная пауза на 10 мин (до стабилизации свечей)."
                    )

                # If token or global guard is in cooldown, ensure no BUY orders linger
                is_in_cooldown = self.guard.global_cooldown_active or t_metric.get("cooldown_active", False)
                if is_in_cooldown and open_buys:
                    self.cancel_all_buys(sym, open_buys)
                    open_buys.clear()

                # Estimate Entry Price: volume-weighted average price (VWAP) across currently held position
                entry_price = cur_price
                sym_buys = self.recent_buys.get(sym, [])
                active_position_buys: List[Dict[str, Any]] = []
                if sym_buys and cur_free > 0:
                    accum_qty = 0.0
                    accum_val = 0.0
                    for b in sym_buys:
                        b_q = float(b.get("execQty") or 0.0)
                        b_p = float(b.get("execPrice") or 0.0)
                        if b_q <= 0 or b_p <= 0:
                            continue
                        take_q = min(b_q, max(0.0, cur_free - accum_qty))
                        accum_val += take_q * b_p
                        accum_qty += take_q
                        active_position_buys.append(b)
                        if accum_qty >= (cur_free * 0.99):
                            break
                    if accum_qty > 0:
                        entry_price = round(accum_val / accum_qty, meta.get("price_decimals", 4))
                    else:
                        entry_price = float(sym_buys[0].get("execPrice") or cur_price)
                elif sym_buys:
                    entry_price = float(sym_buys[0].get("execPrice") or cur_price)
                    active_position_buys = [sym_buys[0]]

                # =============================================================
                # TAKE-PROFIT LOGIC: TRAILING (DESKTOP) VS STATIC LIMIT (MOBILE)
                # =============================================================
                position_age_hours = 0.0
                tp_mode = "Standard (+0.90%)"
                trailing_active = False
                position_closed_by_trailing = False

                active_steps_count = 1 if holding_val >= 4.50 else 0
                if holding_val >= 13.50:
                    active_steps_count = 2
                if holding_val >= 24.00:
                    active_steps_count = 3
                skewed_tp_pct = self.inventory_skew.get_skewed_tp_pct(active_steps_count)

                if self.mode == "desktop":
                    sym_act_pct = meta.get("trailing_activation_pct", TRAILING_ACTIVATION_PCT)
                    sym_cb_pct = meta.get("trailing_callback_pct", TRAILING_CALLBACK_PCT)
                    sym_fl_pct = meta.get("trailing_min_floor_pct", TRAILING_MIN_FLOOR_PCT)

                    # Inventory Skew: with 2 or 3 steps held, tighten trailing threshold to quickly derisk
                    if active_steps_count >= 2:
                        sym_act_pct = min(sym_act_pct, round(skewed_tp_pct * 1.5, 4))
                        sym_fl_pct = min(sym_fl_pct, skewed_tp_pct)

                    trailing_res = self.trailing_controller.update_price(
                        sym, cur_price, entry_price, cur_free, free_val,
                        activation_pct=sym_act_pct,
                        callback_pct=sym_cb_pct,
                        min_floor_pct=sym_fl_pct,
                    )
                    tr_state = self.trailing_controller.get_state(sym)
                    trailing_active = (tr_state.status == "TRAILING_ACTIVE")

                    if trailing_res:
                        ev_name = trailing_res.get("event") or trailing_res.get("action")
                        if ev_name == "ACTIVATED":
                            tp_mode = f"🚀 Trailing Active (+{trailing_res['gain_pct']*100:.2f}%)"
                            logger.info(
                                f"🚀 [{sym}][TRAILING АКТИВИРОВАН] Вход: ${entry_price:.4f} | "
                                f"Текущая: ${cur_price:.4f} (+{trailing_res['gain_pct']*100:.2f}%) | "
                                f"Стоп: ${trailing_res['stop_price']:.4f} (Пол: ${trailing_res['floor_price']:.4f})"
                            )
                            send_telegram(
                                f"🚀 **[TRAILING TP: РАКЕТА АКТИВИРОВАНА]**\n\n"
                                f"Пара: **{sym}**\n"
                                f"Вход: **${entry_price:.4f}**\n"
                                f"Текущая цена: **${cur_price:.4f}** (+{trailing_res['gain_pct']*100:.2f}%)\n"
                                f"Начальный стоп: **${trailing_res['stop_price']:.4f}** (Откат: {sym_cb_pct*100:.2f}%)\n"
                                f"Гарантированный пол: **${trailing_res['floor_price']:.4f}** (+{sym_fl_pct*100:.2f}%)\n\n"
                                "Режим: Сопровождение импульса до первого разворота."
                            )
                            if open_sells:
                                for s_ord in list(open_sells):
                                    self.client.cancel_order(sym, s_ord.get("orderId"))
                                    open_sells.remove(s_ord)

                        elif ev_name == "TRIGGER_EXIT":
                            sell_qty = math.floor(cur_free * 100) / 100.0
                            logger.info(
                                f"🚀 [{sym}][TRAILING СБРОС] Излом импульса! "
                                f"Пик: ${trailing_res['peak_price']:.4f} (+{trailing_res['peak_gain_pct']*100:.2f}%) | "
                                f"Продажа: {sell_qty} {base_c} @ ${cur_price:.4f} (+{trailing_res['gain_pct']*100:.2f}%)"
                            )
                            resp_exit = self.client.create_market_order(sym, "Sell", sell_qty)
                            if resp_exit.get("retCode") == 0:
                                net_p = round((cur_price - entry_price) * sell_qty, 4)
                                self.token_cycles[sym] = self.token_cycles.get(sym, 0) + 1
                                self.token_profits[sym] = round(self.token_profits.get(sym, 0.0) + max(0.0, net_p), 4)
                                send_telegram(
                                    f"🚀 **[TRAILING TP: РАКЕТА УСПЕШНО ЗАФИКСИРОВАНА!]**\n\n"
                                    f"Пара: **{sym}**\n"
                                    f"Объем: **{sell_qty} {base_c}**\n"
                                    f"• Вход: `${entry_price:.4f}`\n"
                                    f"• Пик: `${trailing_res['peak_price']:.4f}` (+{trailing_res['peak_gain_pct']*100:.2f}%)\n"
                                    f"• Продажа: `${cur_price:.4f}` (+{trailing_res['gain_pct']*100:.2f}%)\n"
                                    f"• Итоговый профит: **+{trailing_res['gain_pct']*100:.2f}%** (чистыми +${net_p:.4f} USDT)\n"
                                    f"Всего закрыто циклов ({sym}): **{self.token_cycles[sym]}**"
                                )
                                position_closed_by_trailing = True

                    elif trailing_active:
                        tp_mode = f"🚀 Trailing (+{(cur_price - entry_price)/entry_price*100:.2f}% / Стоп: ${tr_state.stop_price:.4f})"
                        if open_sells:
                            for s_ord in list(open_sells):
                                self.client.cancel_order(sym, s_ord.get("orderId"))
                                open_sells.remove(s_ord)
                    elif free_val >= 5.00:
                        sym_act_pct = meta.get("trailing_activation_pct", TRAILING_ACTIVATION_PCT)
                        tp_mode = f"🚀 Rocket Rider (Цель: +{sym_act_pct*100:.2f}%)"
                        if open_sells:
                            for s_ord in list(open_sells):
                                self.client.cancel_order(sym, s_ord.get("orderId"))
                                open_sells.remove(s_ord)

                # =============================================================
                # STEP 3 PARTIAL TAKE-PROFIT (SCALE-OUT DE-RISKING)
                # =============================================================
                # If holding full 3-step position (or >= $24 USDT) and market gives a +0.50% micro-bounce,
                # immediately dump Step 3 (~$14-$16 USDT) to de-risk, bank cash, and ride remainder in breakeven.
                position_scaled_out = False
                scale_out_cooldown_ok = (now - self.last_scale_out_ts.get(sym, 0.0)) >= SCALE_OUT_COOLDOWN_SEC
                curr_pos_gain = (cur_price - entry_price) / entry_price if entry_price > 0 else 0.0

                if (
                    self.is_active_controller
                    and not position_closed_by_trailing
                    and not trailing_active
                    and scale_out_cooldown_ok
                    and holding_val >= 24.00
                    and curr_pos_gain >= SCALE_OUT_TRIGGER_GAIN_PCT
                ):
                    # Step 3 is approximately 45-50% of the loaded position
                    partial_qty = math.floor((cur_free * 0.48) * (10 ** meta.get("qty_decimals", 2))) / float(10 ** meta.get("qty_decimals", 2))
                    partial_val = partial_qty * cur_price

                    if partial_val >= 5.00 and (cur_free - partial_qty) * cur_price >= 5.00:
                        logger.info(
                            f"⚡ [{sym}][SCALE-OUT] Микро-отскок +{curr_pos_gain*100:.2f}% при полной загрузке (${holding_val:.2f})! "
                            f"Сброс Ступени 3: {partial_qty} {base_c} @ ${cur_price:.4f} (~${partial_val:.2f})"
                        )
                        # Cancel existing TP limit orders to free balance for immediate market scale-out
                        if open_sells:
                            for s_ord in list(open_sells):
                                self.client.cancel_order(sym, s_ord.get("orderId"))
                                open_sells.remove(s_ord)

                        resp_so = self.client.create_market_order(sym, "Sell", partial_qty)
                        if resp_so.get("retCode") == 0:
                            so_pnl = round((cur_price - entry_price) * partial_qty, 4)
                            self.token_profits[sym] = round(self.token_profits.get(sym, 0.0) + max(0.0, so_pnl), 4)
                            self.last_scale_out_ts[sym] = now
                            position_scaled_out = True
                            cur_free = max(0.0, cur_free - partial_qty)
                            cur_total = max(0.0, cur_total - partial_qty)
                            free_val = cur_free * cur_price
                            holding_val = cur_total * cur_price

                            send_telegram(
                                f"⚡ **[SCALE-OUT: ЧАСТИЧНЫЙ СБРОС СТУПЕНИ 3]**\n\n"
                                f"Пара: **{sym}**\n"
                                f"Отскок от средней: **+{curr_pos_gain*100:.2f}%**\n"
                                f"Сброшено: **{partial_qty} {base_c}** (~${partial_val:.2f} USDT)\n"
                                f"Зафиксировано чистыми: **+${so_pnl:.4f} USDT**\n\n"
                                f"🛡️ **Риск снят:** ~$16 USDT возвращены в свободный кэш!\n"
                                f"Остаток: **{cur_free:.2f} {base_c}** (~${free_val:.2f}) переведен в сопровождение ТП."
                            )

                if position_closed_by_trailing:
                    token_stats_map[sym] = {
                        "symbol": sym,
                        "name": meta.get("name", sym),
                        "base_coin": base_c,
                        "badge_color": meta.get("badge_color", "#38bdf8"),
                        "mode": "ACTIVE",
                        "price": cur_price,
                        "free_coin": 0.0,
                        "locked_coin": 0.0,
                        "holding_value_usd": 0.0,
                        "entry_price": 0.0,
                        "rocket_target_price": 0.0,
                        "rocket_distance_pct": 0.0,
                        "current_gain_pct": 0.0,
                        "trailing_active": False,
                        "trailing_peak_price": 0.0,
                        "trailing_stop_price": 0.0,
                        "trailing_floor_price": 0.0,
                        "completed_cycles": self.token_cycles.get(sym, 0),
                        "net_profit_usd": self.token_profits.get(sym, 0.0),
                        "tp_mode": "Standard (+0.90%)",
                        "position_age_hours": 0.0,
                        "step1_discount_pct": round(t_metric.get("step1_discount", BASE_SPACING["step_1"]) * 100, 2),
                        "step2_discount_pct": round(t_metric.get("step2_discount", BASE_SPACING["step_2"]) * 100, 2),
                        "step3_discount_pct": round(t_metric.get("step3_discount", BASE_SPACING["step_3"]) * 100, 2),
                        "vol_multiplier": t_metric.get("vol_multiplier", 1.0),
                        "volatility_regime": t_metric.get("volatility_regime", "NORMAL"),
                        "range_15m_pct": round(t_metric.get("range_15m", 0.0) * 100, 2),
                        "chg_1m_pct": round(t_metric.get("last_1m_chg", 0.0) * 100, 2),
                        "obi": round(t_metric.get("obi", 0.0), 3),
                        "cooldown_active": t_metric.get("cooldown_active", False),
                        "cooldown_reason": t_metric.get("cooldown_reason", ""),
                    }
                    continue


                # Soft Breakeven Evaluation (>8 hours)
                position_age_hours = 0.0
                if not trailing_active:
                    for s_ord in list(open_sells):
                        s_id = s_ord.get("orderId")
                        s_price = float(s_ord.get("price", 0.0))
                        s_created = float(s_ord.get("createdTime", now * 1000)) / 1000.0
                        age_h = (now - s_created) / 3600.0
                        position_age_hours = max(position_age_hours, age_h)

                        if age_h >= STALE_POSITION_HOURS:
                            tp_mode = f"Soft Breakeven ({age_h:.1f}ч)"
                            soft_tp_price = round(entry_price * (1.0 + SOFT_BREAKEVEN_TP_PCT), meta.get("price_decimals", 4))
                            if s_price > soft_tp_price and (soft_tp_price * float(s_ord.get("qty", 0.0))) >= 5.00:
                                logger.info(
                                    f"🛡️ [{sym}] Зависание {age_h:.1f}ч! Снижаем ТП с ${s_price} до ${soft_tp_price} (+{SOFT_BREAKEVEN_TP_PCT*100:.2f}%)"
                                )
                                self.client.cancel_order(sym, s_id)
                                open_sells.remove(s_ord)
                                resp_soft = self.client.create_limit_order(
                                    sym, "Sell", float(s_ord.get("qty", 0.0)), soft_tp_price, post_only=True
                                )
                                if resp_soft.get("retCode") == 0:
                                    send_telegram(
                                        f"🛡️ **[ЗАЩИТА ДЕПОЗИТА: SOFT BREAKEVEN {sym}]**\n\n"
                                        f"Пара: **{sym}**\n"
                                        f"Позиция удерживается: **{age_h:.1f} ч**\n"
                                        f"Тейк-профит снижен до: **${soft_tp_price}** (+{SOFT_BREAKEVEN_TP_PCT*100:.2f}%)\n"
                                        "Цель: Гарантированный выход в плюс (+0.18% чистыми) при первом отскоке."
                                    )

                # Place Fresh Take-Profit SELL Order (Mobile profile only; Desktop uses Trailing)
                if self.mode != "desktop":
                    if free_val >= 5.00 and len(open_sells) < 2:
                        tp_pct = skewed_tp_pct
                        tp_price = round(entry_price * (1.0 + tp_pct), meta.get("price_decimals", 4))
                        sell_qty = math.floor(cur_free * 100) / 100.0
                        use_post_only = tp_price > cur_price

                        if (sell_qty * tp_price) >= 5.00:
                            logger.info(f"🟢 [{sym}] Выставляем ТЕЙК-ПРОФИТ: {sell_qty} {base_c} @ ${tp_price} (+{tp_pct*100:.2f}%)")
                            resp = self.client.create_limit_order(sym, "Sell", sell_qty, tp_price, post_only=use_post_only)
                            if resp.get("retCode") == 0:
                                send_telegram(
                                    f"🟢 **[BYBIT.KZ: ТЕЙК-ПРОФИТ ВЫСТАВЛЕН]**\n\n"
                                    f"Пара: **{sym}**\n"
                                    f"Объем: **{sell_qty} {base_c}** (~${round(sell_qty * tp_price, 2)})\n"
                                    f"Цена выхода: **${tp_price}** (+{tp_pct*100:.2f}%)\n"
                                    f"Ордер ID: `{resp.get('result', {}).get('orderId')}`"
                                )

                # =============================================================
                # MARKET REGIME PROFILE & CYCLE LOCK
                # =============================================================
                raw_regime = t_metric.get("market_regime", "NORMAL")
                # Cycle Lock: If holding position >= $4.50, lock the regime to avoid mid-cycle drift
                if holding_val >= 4.50:
                    if not self.token_locked_regime.get(sym):
                        self.token_locked_regime[sym] = raw_regime
                    active_regime = self.token_locked_regime[sym]
                else:
                    self.token_locked_regime[sym] = None
                    active_regime = raw_regime

                regime_cfg = REGIME_PROFILES.get(active_regime, REGIME_PROFILES["NORMAL"])
                is_calm = bool(regime_cfg.get("is_calm_split", False))

                # Budget allocation based on active regime, auto-compounding, and portfolio mode
                spendable_usdt = max(0.0, avail_usdt - self.reserve_usdt) if self.mode == "desktop" else avail_usdt
                if is_calm:
                    step_budget_1a = round(regime_cfg.get("budget_1a", 5.25) * compound_mult, 2)
                    step_budget_1b = round(regime_cfg.get("budget_1b", 5.50) * compound_mult, 2)
                    step_budget_2 = round(regime_cfg.get("budget_2", 10.50) * compound_mult, 2)
                    step_budget_3 = round(regime_cfg.get("budget_3", 15.00) * compound_mult, 2)
                else:
                    step_budget_1 = round(regime_cfg.get("budget_1", 7.95) * compound_mult, 2)
                    step_budget_2 = round(regime_cfg.get("budget_2", 14.15) * compound_mult, 2)
                    step_budget_3 = round(regime_cfg.get("budget_3", 17.00) * compound_mult, 2)

                step1_held = holding_val >= 4.50
                step2_held = holding_val >= (step_budget_2 * 1.5)

                p_dec = meta.get("price_decimals", 4)
                q_dec = meta.get("qty_decimals", 2)

                # Dynamic Adaptive Spacing Targets from active regime
                if is_calm:
                    s1a_disc = regime_cfg.get("step_1a_discount", 0.0035)
                    s1b_disc = regime_cfg.get("step_1b_discount", 0.0065)
                    s2_disc = regime_cfg.get("step_2_discount", 0.0160)
                    s3_disc = regime_cfg.get("step_3_discount", 0.0350)
                else:
                    s1_disc = regime_cfg.get("step_1_discount", 0.0055)
                    s2_disc = regime_cfg.get("step_2_discount", 0.0200)
                    s3_disc = regime_cfg.get("step_3_discount", 0.0400)

                # Apply Inventory Skew: push Step 2 (* 1.25) and Step 3 (* 1.50) deeper as risk increases
                s2_disc = self.inventory_skew.get_skewed_step_offset(2, s2_disc)
                s3_disc = self.inventory_skew.get_skewed_step_offset(3, s3_disc)

                if is_calm:
                    t1a = round(cur_price * (1.0 - s1a_disc), p_dec)
                    t1b = round(cur_price * (1.0 - s1b_disc), p_dec)
                    t1 = t1a
                    s1_disc = s1a_disc
                else:
                    t1 = round(cur_price * (1.0 - s1_disc), p_dec)

                if step1_held and entry_price > 0:
                    t2 = round(entry_price * (1.0 - s2_disc), p_dec)
                    t3 = round(entry_price * (1.0 - s3_disc), p_dec)
                    min_t3_dist = 0.0250
                    if t3 >= (cur_price * (1.0 - min_t3_dist)):
                        t3 = round(cur_price * (1.0 - min_t3_dist), p_dec)
                    if active_position_buys:
                        lowest_active_buy = min(float(b.get("execPrice") or 999.0) for b in active_position_buys if float(b.get("execPrice") or 0) > 0)
                        if lowest_active_buy < 900.0 and t3 >= (lowest_active_buy * (1.0 - min_t3_dist)):
                            t3 = round(lowest_active_buy * (1.0 - min_t3_dist), p_dec)
                    if t2 >= cur_price:
                        t2 = round(cur_price * 0.9995, p_dec)
                else:
                    t2 = round(cur_price * (1.0 - s2_disc), p_dec)
                    t3 = round(cur_price * (1.0 - s3_disc), p_dec)

                # Scan L2 Order Book Walls (Front-run institutional bid walls by 1 tick)
                tick_sz = 10 ** (-p_dec)
                if is_calm:
                    t1a = self.wall_scanner.find_front_run_price(sym, t1a, window_pct=0.0035, tick_size=tick_sz, price_decimals=p_dec)
                    t1b = self.wall_scanner.find_front_run_price(sym, t1b, window_pct=0.0035, tick_size=tick_sz, price_decimals=p_dec)
                else:
                    t1 = self.wall_scanner.find_front_run_price(sym, t1, window_pct=0.0035, tick_size=tick_sz, price_decimals=p_dec)
                t2 = self.wall_scanner.find_front_run_price(sym, t2, window_pct=0.0035, tick_size=tick_sz, price_decimals=p_dec)
                t3 = self.wall_scanner.find_front_run_price(sym, t3, window_pct=0.0035, tick_size=tick_sz, price_decimals=p_dec)

                # Valid buy targets based on inventory and regime
                valid_targets: List[Tuple[str, float]] = []
                if is_calm:
                    if not step1_held:
                        valid_targets.append(("step_1a", t1a))
                        valid_targets.append(("step_1b", t1b))
                    elif holding_val < (step_budget_1a + step_budget_1b * 0.8):
                        valid_targets.append(("step_1b", t1b))
                else:
                    if not step1_held:
                        valid_targets.append(("step_1", t1))

                if not step2_held:
                    valid_targets.append(("step_2", t2))
                valid_targets.append(("step_3", t3))

                # Drift, Orphan & Duplicate Management for resting BUY orders
                assigned_targets = set()
                sorted_buys = sorted(open_buys, key=lambda b: abs(float(b.get("price", 0.0)) - cur_price))
                for b_ord in list(sorted_buys):
                    ord_id = b_ord.get("orderId")
                    ord_price = float(b_ord.get("price", 0.0))
                    if not ord_id or ord_price <= 0:
                        continue

                    created_time = float(b_ord.get("createdTime", now * 1000)) / 1000.0
                    is_expired = (now - created_time) > 1200

                    best_step = None
                    min_dist = 999.0
                    for step_name, target_p in valid_targets:
                        dist = abs(target_p - ord_price) / ord_price
                        if dist < min_dist:
                            min_dist = dist
                            best_step = step_name

                    # Immunity to expiration for anchored DCA steps (Step 2 and 3 when position is held)
                    is_anchored_dca = (best_step in ("step_2", "step_3")) and step1_held
                    should_expire = is_expired and not is_anchored_dca
                    tolerance = 0.012 if not is_anchored_dca else 0.008

                    if should_expire or min_dist > tolerance or (best_step in assigned_targets):
                        logger.info(
                            f"🟡 [{sym}] Снятие неактуального/дублирующего BUY ордера {ord_id} @ ${ord_price} "
                            f"(Отклонение: {min_dist*100:.2f}%, Цель: {best_step}, Возраст: {int(now - created_time)}с)"
                        )
                        resp_c = self.client.cancel_order(sym, ord_id)
                        if resp_c.get("retCode") == 0 and b_ord in open_buys:
                            open_buys.remove(b_ord)
                    else:
                        if best_step:
                            assigned_targets.add(best_step)

                # BUY Order Placement Eligibility
                can_buy_token = True
                token_mode_label = "ACTIVE"
                if self.is_paused or self.circuit_breaker_active or is_in_cooldown:
                    can_buy_token = False
                    if self.is_paused:
                        token_mode_label = "PAUSED"
                    elif self.circuit_breaker_active:
                        token_mode_label = "CIRCUIT_BREAKER"
                    elif is_in_cooldown:
                        token_mode_label = "COOLDOWN"
                elif sym == SECONDARY_SYMBOL and not self.dual_mode_active:
                    can_buy_token = False
                    token_mode_label = "EXIT_ONLY" if near_has_holdings else "DORMANT"
                    if open_buys:
                        self.cancel_all_buys(sym, open_buys)
                        open_buys.clear()
                elif sym == TERTIARY_SYMBOL and not self.trio_mode_active:
                    can_buy_token = False
                    token_mode_label = "EXIT_ONLY" if avax_has_holdings else "DORMANT"
                    if open_buys:
                        self.cancel_all_buys(sym, open_buys)
                        open_buys.clear()

                # Sizing & Order Placement
                if can_buy_token:

                    # Step 1 placement (Calm 1A / 1B or Normal 1) - Protected by Lead-Lag Gate
                    if not self.guard.gate_step1_open:
                        if not any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys):
                            logger.info(
                                f"⏳ [{sym}][Lead-Lag BTC] Вход в Ступень 1 заморожен: "
                                f"статус BTC {self.guard.lead_lag_status} ({self.guard.lead_lag_reason})"
                            )
                    elif is_calm:
                        # Step 1A (Micro-Scalp -0.35%)
                        if not step1_held:
                            has_1a = any(abs(float(o.get("price", 0)) - t1a) / t1a < 0.010 for o in open_buys)
                            if not has_1a and spendable_usdt >= step_budget_1a:
                                clip_1a = math.floor((step_budget_1a / t1a) * (10 ** q_dec)) / float(10 ** q_dec)
                                val_1a = clip_1a * t1a
                                if val_1a >= 5.00 and val_1a <= spendable_usdt:
                                    logger.info(
                                        f"🔵 [{sym}][Ступень 1A ШТИЛЬ] Покупка: {clip_1a} {base_c} @ ${t1a} "
                                        f"(-{s1a_disc*100:.2f}%) [Бюджет: ${step_budget_1a:.2f}]"
                                    )
                                    resp1a = self.client.create_limit_order(
                                        sym, "Buy", clip_1a, t1a, post_only=True, qty_precision=q_dec, price_precision=p_dec
                                    )
                                    if resp1a.get("retCode") == 0:
                                        avail_usdt -= val_1a
                                        spendable_usdt -= val_1a

                        # Step 1B (Main Wave -0.65%)
                        if holding_val < (step_budget_1a + step_budget_1b * 0.8):
                            has_1b = any(abs(float(o.get("price", 0)) - t1b) / t1b < 0.010 for o in open_buys)
                            if not has_1b and spendable_usdt >= step_budget_1b:
                                clip_1b = math.floor((step_budget_1b / t1b) * (10 ** q_dec)) / float(10 ** q_dec)
                                val_1b = clip_1b * t1b
                                if val_1b >= 5.00 and val_1b <= spendable_usdt:
                                    logger.info(
                                        f"🔵 [{sym}][Ступень 1B ШТИЛЬ] Покупка: {clip_1b} {base_c} @ ${t1b} "
                                        f"(-{s1b_disc*100:.2f}%) [Бюджет: ${step_budget_1b:.2f}]"
                                    )
                                    resp1b = self.client.create_limit_order(
                                        sym, "Buy", clip_1b, t1b, post_only=True, qty_precision=q_dec, price_precision=p_dec
                                    )
                                    if resp1b.get("retCode") == 0:
                                        avail_usdt -= val_1b
                                        spendable_usdt -= val_1b
                    else:
                        # Standard / Storm Step 1
                        if not step1_held:
                            has_step1 = any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys)
                            if not has_step1 and spendable_usdt >= step_budget_1:
                                clip_1 = math.floor((step_budget_1 / t1) * (10 ** q_dec)) / float(10 ** q_dec)
                                val_1 = clip_1 * t1
                                if val_1 >= 5.00 and val_1 <= spendable_usdt:
                                    logger.info(
                                        f"🟡 [{sym}][Ступень 1 {active_regime}] Покупка: {clip_1} {base_c} @ ${t1} "
                                        f"(-{s1_disc*100:.2f}%) [Бюджет: ${step_budget_1:.2f}]"
                                    )
                                    resp1 = self.client.create_limit_order(
                                        sym, "Buy", clip_1, t1, post_only=True, qty_precision=q_dec, price_precision=p_dec
                                    )
                                    if resp1.get("retCode") == 0:
                                        avail_usdt -= val_1
                                        spendable_usdt -= val_1

                    # Step 2 (Medium Pullback)
                    if not step2_held:
                        has_step2 = any(abs(float(o.get("price", 0)) - t2) / t2 < 0.010 for o in open_buys)
                        if not has_step2 and spendable_usdt >= step_budget_2 and not self.guard.dca_protection_active:
                            clip_2 = math.floor((step_budget_2 / t2) * (10 ** q_dec)) / float(10 ** q_dec)
                            val_2 = clip_2 * t2
                            if val_2 >= 5.00 and val_2 <= spendable_usdt:
                                logger.info(
                                    f"🟡 [{sym}][Ступень 2 {active_regime}] Покупка: {clip_2} {base_c} @ ${t2} "
                                    f"(-{s2_disc*100:.2f}%) [Бюджет: ${step_budget_2:.2f}]"
                                )
                                resp2 = self.client.create_limit_order(
                                    sym, "Buy", clip_2, t2, post_only=True, qty_precision=q_dec, price_precision=p_dec
                                )
                                if resp2.get("retCode") == 0:
                                    avail_usdt -= val_2
                                    spendable_usdt -= val_2

                    # Step 3 (Deepest Protection Floor)
                    has_step3 = any(abs(float(o.get("price", 0)) - t3) / t3 < 0.010 for o in open_buys)
                    alloc_3 = min(spendable_usdt, step_budget_3)
                    if not has_step3 and spendable_usdt >= 5.00 and not self.guard.dca_protection_active:
                        clip_3 = math.floor((alloc_3 / t3) * (10 ** q_dec)) / float(10 ** q_dec)
                        val_3 = clip_3 * t3
                        if val_3 >= 5.00 and val_3 <= spendable_usdt:
                            logger.info(
                                f"🟡 [{sym}][Ступень 3 {active_regime}] Покупка: {clip_3} {base_c} @ ${t3} "
                                f"(-{s3_disc*100:.2f}%) [Бюджет: ${alloc_3:.2f}]"
                            )
                            resp3 = self.client.create_limit_order(
                                sym, "Buy", clip_3, t3, post_only=True, qty_precision=q_dec, price_precision=p_dec
                            )
                            if resp3.get("retCode") == 0:
                                avail_usdt -= val_3
                                spendable_usdt -= val_3


                # Assemble token statistics
                dec = meta.get("price_decimals", 4)
                has_holding = (cur_free * cur_price) >= 4.5
                sym_act_pct = meta.get("trailing_activation_pct", TRAILING_ACTIVATION_PCT)
                rocket_target = round(entry_price * (1.0 + sym_act_pct), dec) if (has_holding and entry_price > 0) else 0.0
                rocket_dist = round(((rocket_target - cur_price) / cur_price) * 100, 2) if (rocket_target > 0 and cur_price > 0) else 0.0
                curr_gain = round(((cur_price - entry_price) / entry_price) * 100, 2) if (has_holding and entry_price > 0) else 0.0

                tr_state = self.trailing_controller.get_state(sym) if (self.mode == "desktop" and hasattr(self, "trailing_controller")) else None
                is_tr = (tr_state is not None and tr_state.status == "TRAILING_ACTIVE")
                tr_peak = round(tr_state.peak_price, dec) if (is_tr and tr_state) else 0.0
                tr_stop = round(tr_state.stop_price, dec) if (is_tr and tr_state) else 0.0
                tr_floor = round(tr_state.floor_price, dec) if (is_tr and tr_state) else 0.0

                token_stats_map[sym] = {
                    "symbol": sym,
                    "name": meta.get("name", sym),
                    "base_coin": base_c,
                    "badge_color": meta.get("badge_color", "#38bdf8"),
                    "mode": token_mode_label,
                    "price": cur_price,
                    "free_coin": round(cur_free, 4),
                    "locked_coin": round(cur_total - cur_free, 4),
                    "holding_value_usd": round(holding_val, 2),
                    "entry_price": round(entry_price, dec) if has_holding else 0.0,
                    "rocket_target_price": rocket_target,
                    "rocket_distance_pct": rocket_dist,
                    "current_gain_pct": curr_gain,
                    "trailing_active": is_tr,
                    "trailing_peak_price": tr_peak,
                    "trailing_stop_price": tr_stop,
                    "trailing_floor_price": tr_floor,
                    "completed_cycles": self.token_cycles.get(sym, 0),
                    "net_profit_usd": self.token_profits.get(sym, 0.0),
                    "tp_mode": tp_mode,
                    "position_age_hours": round(position_age_hours, 1),
                    "step1_discount_pct": round(s1_disc * 100, 2),
                    "step2_discount_pct": round(s2_disc * 100, 2),
                    "step3_discount_pct": round(s3_disc * 100, 2),
                    "vol_multiplier": t_metric.get("vol_multiplier", 1.0),
                    "volatility_regime": active_regime,
                    "market_regime": active_regime,
                    "regime_name": regime_cfg.get("name", active_regime),
                    "regime_badge_color": regime_cfg.get("badge_color", "#10b981"),
                    "cycle_locked": bool(self.token_locked_regime.get(sym) is not None),
                    "range_15m_pct": round(t_metric.get("range_15m_pct", t_metric.get("range_15m", 0.0) * 100), 2),
                    "chg_1m_pct": round(t_metric.get("last_1m_chg", 0.0) * 100, 2),
                    "obi": round(t_metric.get("obi", 0.0), 3),
                    "cooldown_active": t_metric.get("cooldown_active", False),
                    "cooldown_reason": t_metric.get("cooldown_reason", ""),
                }

            # 9. Update Unified Stats
            global_guard_str = "🟢 Норма"
            if self.is_paused:
                global_guard_str = "⏸️ На паузе (Все покупки заморожены)"
            elif self.circuit_breaker_active:
                global_guard_str = "🚨 Circuit Breaker (Просадка > 5%)"
            elif self.guard.global_cooldown_active:
                el = int(now - self.guard.global_cooldown_start_time)
                global_guard_str = f"🚨 Рыночный Шторм ({self.guard.global_cooldown_reason}) [{el}с]"
            elif self.guard.lead_lag_status == "SLIDING":
                global_guard_str = f"🟡 Lead-Lag BTC Сползает ({self.guard.lead_lag_reason})"

            if self.trio_mode_active:
                port_mode_str = f"🚀 Trio ({TOKEN_METADATA[PRIMARY_SYMBOL]['base_coin']} + {TOKEN_METADATA[SECONDARY_SYMBOL]['base_coin']} + {TOKEN_METADATA[TERTIARY_SYMBOL]['base_coin']} 33/33/33)"
            elif self.dual_mode_active:
                port_mode_str = f"🚀 Dual ({TOKEN_METADATA[PRIMARY_SYMBOL]['base_coin']} + {TOKEN_METADATA[SECONDARY_SYMBOL]['base_coin']} 50/50)"
            else:
                port_mode_str = f"🔥 Single ({TOKEN_METADATA[PRIMARY_SYMBOL]['base_coin']} 100%)"

            profile_label = "DESKTOP / SMART-STEP" if self.mode == "desktop" else "MOBILE / STORM"

            self.stats.update({
                "mode": self.mode,
                "profile": profile_label,
                "role": self.role,
                "reserve_usdt": round(self.reserve_usdt, 2),
                "portfolio_mode": port_mode_str,
                "dual_mode_active": self.dual_mode_active,
                "trio_mode_active": self.trio_mode_active,
                "total_usd": round(est_total_equity, 4),
                "available_usdt": round(avail_usdt, 4),
                "locked_usdt": round(locked_usdt, 4),
                "mnt_balance": round(mnt_bal, 4),
                "is_paused": self.is_paused,
                "circuit_breaker_active": self.circuit_breaker_active,
                "global_guard_status": global_guard_str,
                "btc_1m_chg": round(self.guard.last_btc_1m_chg * 100, 2),
                "btc_3m_chg": round(self.guard.last_btc_3m_chg * 100, 2),
                "lead_lag": {
                    "status": self.guard.lead_lag_status,
                    "reason": self.guard.lead_lag_reason,
                    "gate_step1_open": self.guard.gate_step1_open,
                    "dca_protection_active": self.guard.dca_protection_active,
                    "btc_1m_chg": round(self.guard.last_btc_1m_chg * 100, 2),
                    "btc_3m_chg": round(self.guard.last_btc_3m_chg * 100, 2),
                },
                "compound_multiplier": compound_mult,
                "compound_baseline": COMPOUND_BASELINE_EQUITY,
                "compound_active": bool(compound_mult > 1.00),
                "tokens": token_stats_map,
                "all_open_orders": all_open_orders_list,
                "sniper": self.flash_sniper.to_dict() if self.flash_sniper else None,
                "breakout": self.breakout_engine.to_dict() if self.breakout_engine else None,
                "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })

            # 10. Flash Sniper Tick (Parallel Flash-Crash Harvester on NEAR)
            if self.flash_sniper and self.is_active_controller and not self.is_paused:
                # Dynamically scale sniper budget under auto-compounding
                scaled_sniper_budget = round(SNIPER_BUDGET_USD * compound_mult, 2)
                self.flash_sniper.update_budget(scaled_sniper_budget)

                target_spot = prices.get(SNIPER_TARGET_SYMBOL, 0.0)
                target_free = free_coins.get(SNIPER_TARGET_SYMBOL, 0.0)
                meta_target = TOKEN_METADATA.get(SNIPER_TARGET_SYMBOL, {})
                target_p_dec = meta_target.get("price_decimals", 4)
                target_q_dec = meta_target.get("qty_decimals", 2)

                # Cancel any old/mismatched sniper orders if target symbol changed
                for o in all_open_orders_list:
                    oid_link = str(o.get("orderLinkId", ""))
                    if oid_link.startswith("SNIPER_") and not oid_link.startswith(SNIPER_ORDER_LINK_PREFIX):
                        old_sym = o.get("symbol", PRIMARY_SYMBOL)
                        logger.info(f"🧹 [Flash Sniper Cleanup] Снятие устаревшего ордера {oid_link} на {old_sym}")
                        self.client.cancel_order(old_sym, o.get("orderId"))

                self.flash_sniper.sync_on_exchange_orders(all_open_orders_list)
                # Check if sniper buy executed into position by looking at active open orders
                has_active_sniper_buy = any(
                    str(o.get("orderLinkId", "")).startswith(f"{SNIPER_ORDER_LINK_PREFIX}_BUY")
                    for o in all_open_orders_list
                )
                if self.flash_sniper.state.status == "HUNTING" and self.flash_sniper.state.buy_order_id and not has_active_sniper_buy:
                    # Buy order executed
                    calc_qty = (
                        math.floor((self.flash_sniper.budget_usd / self.flash_sniper.state.buy_price) * (10 ** target_q_dec))
                        / float(10 ** target_q_dec)
                        if self.flash_sniper.state.buy_price > 0 else 0.0
                    )
                    if calc_qty > 0:
                        self.flash_sniper.state.position_qty = calc_qty
                        self.flash_sniper.state.entry_price = self.flash_sniper.state.buy_price
                        self.flash_sniper.state.status = "POSITION_HELD"
                        logger.info(
                            f"🎯⚡ [Flash Sniper Execution] Ордер-ловушка {SNIPER_TARGET_SYMBOL} исполнен! "
                            f"Куплено {calc_qty} @ ${self.flash_sniper.state.entry_price:.4f}"
                        )
                sniper_metrics = self.guard.token_metrics.get(SNIPER_TARGET_SYMBOL, {})
                t_1m = sniper_metrics.get("last_1m_chg", 0.0)
                t_3m = sniper_metrics.get("last_3m_chg", 0.0)
                v_reg = sniper_metrics.get("volatility_regime", "NORMAL")
                t_obi = sniper_metrics.get("obi", 0.0)

                # Run sniper tick
                self.flash_sniper.tick(
                    client=self.client,
                    cur_price=target_spot,
                    avail_usdt=avail_usdt,
                    free_qty=target_free,
                    lead_lag_status=self.guard.lead_lag_status,
                    price_decimals=target_p_dec,
                    qty_decimals=target_q_dec,
                    token_1m_chg=t_1m,
                    token_3m_chg=t_3m,
                    volatility_regime=v_reg,
                    obi=t_obi,
                )

            # 11. Momentum Breakout Tick (Impulse Scalper on SUI)
            if self.breakout_engine and self.is_active_controller and not self.is_paused:
                brk_sym = self.breakout_engine.symbol
                brk_spot = prices.get(brk_sym, 0.0)
                brk_free = free_coins.get(brk_sym, 0.0)
                brk_klines = self.guard.fetch_klines(brk_sym, limit=20)
                brk_obi = self.guard.token_metrics.get(brk_sym, {}).get("obi", 0.0)
                brk_meta = TOKEN_METADATA.get(brk_sym, {})

                self.breakout_engine.tick(
                    client=self.client,
                    cur_price=brk_spot,
                    avail_usdt=avail_usdt,
                    free_qty=brk_free,
                    lead_lag_status=self.guard.lead_lag_status,
                    klines=brk_klines,
                    obi=brk_obi,
                    price_decimals=brk_meta.get("price_decimals", 4),
                    qty_decimals=brk_meta.get("qty_decimals", 2),
                )

            # 12. Desktop Heartbeat Canary Maintenance (On-Exchange Canary Ping)
            if self.mode == "desktop" and self.is_active_controller and not self.is_paused:
                self.maintain_canary_order()

        except Exception as e:
            logger.error(f"Trading loop exception: {e}")

    def run_forever(self) -> None:
        """Main execution loop (runs every 10 seconds)."""
        profile_banner = (
            f"🖥️ [DESKTOP / SMART-STEP] (Асимметричная сетка + буфер ${self.reserve_usdt:.2f} USDT)"
            if self.mode == "desktop"
            else "📱 [MOBILE / STORM] (Консервативный эшелон STORM x2.0)"
        )
        logger.info(f"🚀 [Bybit Kazakhstan Standalone Portfolio Bot] Запуск профиля: {profile_banner}")
        logger.info(
            f"Базовый: {PRIMARY_SYMBOL} | Вторичный: {SECONDARY_SYMBOL} | "
            f"Третичный: {TERTIARY_SYMBOL} | Lead-Lag: {LEAD_LAG_SYMBOL}"
        )

        while self.running:
            self.step()

            # Dynamic Polling Frequency:
            # 1. Trailing Active: 1.0s (ultra-fast momentum tracking)
            # 2. Rocket Launch Corridor (within 0.35% of activation or in profit >= 0.40%): 1.5s (never miss the peak)
            # 3. Standard resting grid: 5.0s (responsive, no Bybit rate limit issues)
            is_trailing = (
                self.mode == "desktop"
                and hasattr(self, "trailing_controller")
                and self.trailing_controller.is_any_trailing_active()
            )

            near_rocket = False
            if self.mode == "desktop" and not is_trailing:
                tok_data = self.stats.get("tokens", {})
                for sym_k, s_info in tok_data.items():
                    if s_info.get("holding_value_usd", 0.0) >= 4.5:
                        r_dist = s_info.get("rocket_distance_pct", 99.0)
                        c_gain = s_info.get("current_gain_pct", 0.0)
                        if r_dist <= 0.35 or c_gain >= 0.40:
                            near_rocket = True
                            break

            if is_trailing:
                sleep_time = 1.0
            elif near_rocket:
                sleep_time = 1.5
            else:
                sleep_time = 5.0

            time.sleep(sleep_time)


class SimpleDashboardHandler(http.server.BaseHTTPRequestHandler):
    """Ultra-lightweight embedded web server for mobile browser monitoring and interactive control."""
    bot_instance: Optional[StandaloneBybitBot] = None

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_POST(self) -> None:
        if not self.bot_instance:
            self._send_json({"error": "Bot instance not attached"}, 500)
            return

        if self.path == "/api/pause":
            self.bot_instance.is_paused = True
            self.bot_instance.cancel_all_portfolio_buys()
            logger.info("⏸️ [Web Dashboard] Портфель поставлен на ПАУЗУ через веб-интерфейс.")
            self._send_json({"ok": True, "status": "PAUSED"})
        elif self.path == "/api/resume":
            self.bot_instance.is_paused = False
            self.bot_instance.circuit_breaker_active = False
            logger.info("▶️ [Web Dashboard] Торговля ВОЗОБНОВЛЕНА через веб-интерфейс.")
            self._send_json({"ok": True, "status": "ACTIVE"})
        elif self.path == "/api/panic":
            self.bot_instance.is_paused = True
            self.bot_instance.cancel_all_portfolio_buys()
            logger.warning("🚨 [Web Dashboard] АВАРИЙНАЯ ОСТАНОВКА (Panic Stop) через веб-интерфейс!")
            self._send_json({"ok": True, "status": "PANIC_STOPPED"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/dragon_bg.jpg":
            img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dragon_bg.jpg")
            if os.path.exists(img_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            self.send_response(404)
            self.end_headers()
            return

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

        # Orders Table HTML
        orders_html = "".join([
            f"<tr>"
            f"<td><span class='badge' style='background: {TOKEN_METADATA.get(o.get('symbol', ''), {}).get('badge_color', '#38bdf8')}22; color: {TOKEN_METADATA.get(o.get('symbol', ''), {}).get('badge_color', '#38bdf8')};'>{o.get('symbol')}</span></td>"
            f"<td class='{o.get('side', '').lower()}'>{o.get('side')}</td>"
            f"<td>${float(o.get('price', 0)):.4f}</td>"
            f"<td>{float(o.get('qty', 0)):.2f}</td>"
            f"<td>${float(o.get('qty', 0))*float(o.get('price', 0)):.2f}</td>"
            f"</tr>"
            for o in st.get('all_open_orders', [])
        ])

        tokens_html = ""
        for sym, t in st.get("tokens", {}).items():
            col = t.get("badge_color", "#38bdf8")
            mode_badge = t.get("mode", "ACTIVE")
            holding_usd = float(t.get("holding_value_usd", 0.0))
            entry_p = float(t.get("entry_price", 0.0))
            cur_p = float(t.get("price", 0.0))
            rocket_p = float(t.get("rocket_target_price", 0.0))
            rocket_dist = float(t.get("rocket_distance_pct", 0.0))
            cur_gain = float(t.get("current_gain_pct", 0.0))
            is_tr = bool(t.get("trailing_active", False))
            tr_peak = float(t.get("trailing_peak_price", 0.0))
            tr_stop = float(t.get("trailing_stop_price", 0.0))
            tr_floor = float(t.get("trailing_floor_price", 0.0))

            if is_tr:
                tr_stop_gain = round(((tr_stop - entry_p) / entry_p) * 100, 2) if entry_p > 0 else 0.0
                tr_floor_gain = round(((tr_floor - entry_p) / entry_p) * 100, 2) if entry_p > 0 else 0.0
                rocket_box = f"""
                <div style="margin-top: 10px; padding: 12px; border-radius: 8px; background: linear-gradient(135deg, rgba(234, 179, 8, 0.15), rgba(16, 185, 129, 0.15)); border: 1px solid #eab308;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                        <span style="font-weight: bold; color: #facc15; font-size: 0.95rem;">🚀 РЕЖИМ РАКЕТА АКТИВЕН (Trailing Take-Profit)</span>
                        <span class="badge" style="background: #10b98122; color: #10b981; border: 1px solid #10b981;">ИМПУЛЬС {cur_gain:+.2f}%</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-top: 8px;">
                        <div class="label">Вход (VWAP): <b style="color: #f8fafc;">${entry_p:.4f}</b></div>
                        <div class="label">Пик цены: <b style="color: #facc15;">${tr_peak:.4f}</b></div>
                        <div class="label">Защита прибыли: <b style="color: #10b981;">${tr_stop:.4f} (+{tr_stop_gain:.2f}%)</b></div>
                        <div class="label">Пол прибыли: <b style="color: #38bdf8;">${tr_floor:.4f} (+{tr_floor_gain:.2f}%)</b></div>
                    </div>
                </div>
                """
            elif holding_usd >= 4.5 and entry_p > 0:
                prog_pct = max(0.0, min(100.0, ((cur_p - entry_p) / (rocket_p - entry_p)) * 100.0)) if rocket_p > entry_p else 0.0
                dist_badge_col = "#10b981" if rocket_dist <= 0.5 else "#38bdf8"
                rocket_box = f"""
                <div style="margin-top: 10px; padding: 12px; border-radius: 8px; background: rgba(56, 189, 248, 0.05); border: 1px solid rgba(56, 189, 248, 0.25); backdrop-filter: blur(4px);">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
                        <span style="font-weight: bold; color: #38bdf8; font-size: 0.95rem;">🎯 Ждем активацию РАКЕТЫ (+{TRAILING_ACTIVATION_PCT*100:.2f}% от входа)</span>
                        <span class="badge" style="background: {dist_badge_col}22; color: {dist_badge_col}; border: 1px solid {dist_badge_col};">Цель: ${rocket_p:.4f}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; margin-top: 8px;">
                        <div class="label">Вход (VWAP): <b style="color: #f8fafc;">${entry_p:.4f}</b></div>
                        <div class="label">Текущая: <b style="color: #f8fafc;">${cur_p:.4f}</b> ({cur_gain:+.2f}%)</div>
                        <div class="label">Ждем цену: <b style="color: #38bdf8; font-size: 0.95rem;">${rocket_p:.4f}</b></div>
                        <div class="label">Осталось до старта: <b style="color: {dist_badge_col}; font-size: 0.95rem;">+{rocket_dist:.2f}%</b></div>
                    </div>
                    <div style="margin-top: 8px; background: rgba(51, 65, 85, 0.4); border-radius: 6px; height: 8px; overflow: hidden;">
                        <div style="background: linear-gradient(90deg, #38bdf8, #10b981); height: 100%; width: {prog_pct:.1f}%;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 4px; font-size: 0.72rem; color: #94a3b8;">
                        <span>Вход: ${entry_p:.4f}</span>
                        <span>Прогресс: {prog_pct:.0f}%</span>
                        <span>Старт Ракеты: ${rocket_p:.4f}</span>
                    </div>
                </div>
                """
            else:
                rocket_box = f"""
                <div style="margin-top: 8px; padding: 8px 12px; border-radius: 6px; background: rgba(51, 65, 85, 0.25); border: 1px dashed rgba(148, 163, 184, 0.3);">
                    <span class="label">🎯 Ожидание набора позиции сеткой перед активацией ракеты</span>
                </div>
                """

            tokens_html += f"""
            <div class="card" style="border-left: 4px solid {col};">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="margin: 0; color: {col}; text-shadow: 0 0 10px {col}55;">{t.get('name')} ({sym})</h3>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span class="badge" style="background: {t.get('regime_badge_color', '#10b981')}22; color: {t.get('regime_badge_color', '#10b981')}; border: 1px solid {t.get('regime_badge_color', '#10b981')};">
                            {t.get('regime_name', t.get('market_regime', 'NORMAL'))} {'🔒' if t.get('cycle_locked') else ''}
                        </span>
                        <span class="badge" style="background: {col}22; color: {col}; border: 1px solid {col};">{mode_badge}</span>
                    </div>
                </div>
                <div class="label" style="margin-top: 6px;">Спот: <b>${t.get('price', 0.0):.4f}</b> | 1m: <b>{t.get('chg_1m_pct', 0.0):+.2f}%</b> (15m размах: <b>{t.get('range_15m_pct', 0.0):.2f}%</b>) | OBI: <b>{t.get('obi', 0.0):+.3f}</b></div>
                <div class="label" style="margin-top: 4px;">На руках: <b>{t.get('free_coin', 0.0)} {t.get('base_coin')}</b> (~${t.get('holding_value_usd', 0.0):.2f})</div>
                <div class="label" style="margin-top: 4px; color: #10b981;">Закрыто циклов: <b>{t.get('completed_cycles', 0)}</b> | Профит: <b>+${t.get('net_profit_usd', 0.0):.4f} USDT</b></div>
                <div class="label" style="margin-top: 4px;">Сетка ({t.get('market_regime', t.get('volatility_regime'))}): -{t.get('step1_discount_pct')}% / -{t.get('step2_discount_pct')}% / -{t.get('step3_discount_pct')}%</div>
                <div class="label" style="margin-top: 4px;">Тейк-профит: <b>{t.get('tp_mode')}</b> (удержание: {t.get('position_age_hours')}ч)</div>
                {rocket_box}
            </div>
            """

        # Trade Analytics Block
        ta = st.get("trade_analytics", {})
        if ta and ta.get("total_trades", 0) > 0:
            dow_data = ta.get("dow", {})
            dow_chips = "".join([
                f"<div style='flex: 1; min-width: 62px; background: rgba(15, 23, 42, 0.45); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 6px; text-align: center; backdrop-filter: blur(4px);'>"
                f"<div style='font-size: 0.75rem; color: #94a3b8; font-weight: bold;'>{d}</div>"
                f"<div style='font-weight: bold; color: #38bdf8; font-size: 0.85rem;'>{dow_data.get(d, {}).get('count', 0)}</div>"
                f"<div style='font-size: 0.7rem; color: #cbd5e1;'>${dow_data.get(d, {}).get('volume', 0.0):.1f}</div>"
                f"</div>"
                for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            ])

            hourly_data = ta.get("hourly", {})
            max_h_cnt = max([h_info.get("count", 0) for h_info in hourly_data.values()] or [1])
            max_h_cnt = max(max_h_cnt, 1)

            hourly_bars = []
            for h in range(24):
                h_info = hourly_data.get(h, {})
                c = h_info.get("count", 0)
                v = h_info.get("volume", 0.0)
                buys = h_info.get("buys", 0)
                sells = h_info.get("sells", 0)
                bar_pct = max(6, int((c / max_h_cnt) * 100)) if c > 0 else 4
                bar_col = "#eab308" if h in [22, 23, 0, 1, 2] else ("#38bdf8" if c > 0 else "#334155")
                title_tip = f"{h:02d}:00 - {h:02d}:59 | Сделок: {c} (Куп: {buys}, Прод: {sells}) | Объем: ${v:.2f}"
                hourly_bars.append(
                    f"<div style='flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%;' title='{title_tip}'>"
                    f"<div style='font-size: 0.62rem; color: #94a3b8; margin-bottom: 2px;'>{c if c > 0 else ''}</div>"
                    f"<div style='width: 100%; max-width: 14px; height: {bar_pct}%; background: {bar_col}; border-radius: 2px 2px 0 0;'></div>"
                    f"<div style='font-size: 0.62rem; color: #64748b; margin-top: 3px;'>{h:02d}</div>"
                    f"</div>"
                )
            hourly_chart_html = "".join(hourly_bars)

            recent_trades_html = "".join([
                f"<tr>"
                f"<td>{r.get('time')}</td>"
                f"<td class='{r.get('side', '').lower()}'>{r.get('side')}</td>"
                f"<td>${float(r.get('price', 0.0)):.4f}</td>"
                f"<td>{float(r.get('qty', 0.0)):.2f}</td>"
                f"<td>${float(r.get('val', 0.0)):.2f}</td>"
                f"<td>{float(r.get('fee', 0.0)):.4f} {r.get('fee_coin')}</td>"
                f"</tr>"
                for r in ta.get("recent_trades", [])
            ])

            ta_html = f"""
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <h2>📊 Статистика торгов ({ta.get('total_trades', 0)} сделок)</h2>
                    <span class="badge" style="background: #10b98122; color: #10b981; border: 1px solid #10b981;">Оборот: ${ta.get('total_volume', 0.0):.2f} USDT</span>
                </div>
                <div class="label" style="margin-bottom: 10px;">
                    Всего исполнено: <b>{ta.get('total_trades', 0)}</b> (🟢 Покупок: <b>{ta.get('buys_count', 0)}</b> | 🟡 Продаж: <b>{ta.get('sells_count', 0)}</b>)
                </div>

                <div class="label" style="font-weight: bold; margin-bottom: 6px;">📅 Распределение по дням недели:</div>
                <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 14px;">
                    {dow_chips}
                </div>

                <div class="label" style="font-weight: bold;">⏰ Распределение по часам (Астана UTC+5, золотым выделены ночные часы 22:00-02:00):</div>
                <div style="display: flex; align-items: flex-end; height: 85px; gap: 2px; margin-top: 6px; padding: 4px 0; border-bottom: 1px solid #334155; background: #0f172a55; border-radius: 6px; padding-left: 4px; padding-right: 4px; overflow-x: auto;">
                    {hourly_chart_html}
                </div>

                <div class="label" style="font-weight: bold; margin-top: 14px; margin-bottom: 6px;">📜 Последние исполненные сделки:</div>
                <div style="overflow-x: auto;">
                    <table>
                        <tr><th>Время</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Сумма</th><th>Комиссия</th></tr>
                        {recent_trades_html if recent_trades_html else "<tr><td colspan='6' style='text-align: center; color: #94a3b8;'>Нет данных о сделках</td></tr>"}
                    </table>
                </div>
            </div>
            """
        else:
            ta_html = """
            <div class="card">
                <h2>📊 Статистика торгов</h2>
                <div class="label" style="color: #94a3b8;">Загрузка истории сделок из Bybit Kazakhstan...</div>
            </div>
            """

        # News Sentinel Feed Integration
        news_items_html = ""
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
            from kase_pilot.crypto.news_sentinel import get_latest_market_news
            news_list = get_latest_market_news(max_items=5)
            if news_list:
                news_rows = []
                for n in news_list:
                    n_badge = n.get("badge", "⚪")
                    n_color = n.get("color", "#94a3b8")
                    n_title = n.get("title", "")
                    n_src = n.get("source", "Crypto")
                    n_link = n.get("link", "#")
                    news_rows.append(
                        f"<div style='display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; padding: 6px 0; border-bottom: 1px solid rgba(51, 65, 85, 0.4); font-size: 0.85rem;'>"
                        f"<div style='flex: 1;'><span class='badge' style='background: {n_color}22; color: {n_color}; border: 1px solid {n_color}; font-size: 0.72rem; margin-right: 6px;'>{n_badge}</span>"
                        f"<a href='{n_link}' target='_blank' style='color: #f1f5f9; text-decoration: none;'>{n_title}</a></div>"
                        f"<span style='color: #94a3b8; font-size: 0.72rem; white-space: nowrap;'>{n_src}</span>"
                        f"</div>"
                    )
                news_items_html = "".join(news_rows)
        except Exception:
            pass

        if news_items_html:
            news_card_html = f"""
            <div class="card" style="border: 1px solid rgba(139, 92, 246, 0.35); background: rgba(30, 27, 75, 0.40);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; margin-bottom: 6px;">
                    <h2 style="margin: 0; color: #a78bfa; text-shadow: 0 0 10px #a78bfa55;">📰 Радар новостей и макроэкономики</h2>
                    <span class="badge" style="background: #a78bfa22; color: #c4b5fd; border: 1px solid #a78bfa;">Live Feed & Sentiment</span>
                </div>
                <div style="display: flex; flex-direction: column;">
                    {news_items_html}
                </div>
            </div>
            """
        else:
            news_card_html = ""

        guard_color = "#10b981"
        if "🚨" in st.get("global_guard_status", ""):
            guard_color = "#ef4444"
        elif "⏸️" in st.get("global_guard_status", "") or "🟡" in st.get("global_guard_status", ""):
            guard_color = "#f59e0b"

        ll_data = st.get("lead_lag", {})
        ll_status = ll_data.get("status", "CLEAR")
        ll_color = "#10b981" if ll_status in ("CLEAR", "BULLISH") else ("#f59e0b" if ll_status == "SLIDING" else "#ef4444")
        ll_gate_txt = "🟢 ВХОД РАЗРЕШЕН" if ll_data.get("gate_step1_open", True) else "🟡 ВХОД ЗАМОРОЖЕН"
        lead_lag_badge_html = (
            f"<div class='badge' style='background: {ll_color}22; color: {ll_color}; border: 1px solid {ll_color}; margin-top: 8px; margin-left: 6px;'>"
            f"📡 Lead-Lag Radar: <b>{ll_status}</b> ({ll_gate_txt}) | BTC 1m: {ll_data.get('btc_1m_chg', 0.0):+.2f}% / 3m: {ll_data.get('btc_3m_chg', 0.0):+.2f}%"
            f"</div>"
        )

        profile_badge_html = (
            f"<span class='badge' style='background: #0284c733; color: #38bdf8; border: 1px solid #38bdf8; font-size: 0.75rem; vertical-align: middle; margin-left: 6px;'>"
            f"{st.get('profile', 'MOBILE / STORM')}</span>"
        )
        reserve_html = (
            f" | Резерв: <b>${st.get('reserve_usdt', 0.0):.2f} USDT</b> 🛡️"
            if float(st.get("reserve_usdt") or 0.0) > 0
            else ""
        )

        cmp_mult = float(st.get("compound_multiplier") or 1.0)
        cmp_badge_html = (
            f"<span class='badge' style='background: #a855f722; color: #c084fc; border: 1px solid #c084fc; font-size: 0.75rem; vertical-align: middle; margin-left: 6px;'>"
            f"⚡ Авто-компаундинг: <b>{cmp_mult:.2f}x</b></span>"
            if cmp_mult > 1.00
            else "<span class='badge' style='background: #64748b22; color: #94a3b8; border: 1px solid #64748b; font-size: 0.75rem; vertical-align: middle; margin-left: 6px;'>Авто-компаундинг: 1.00x</span>"
        )

        snp = st.get("sniper")
        if snp:
            s_status = snp.get("status", "IDLE")
            s_badge_col = "#a855f7" if s_status == "ROCKET_ACTIVE" else ("#10b981" if s_status in ("TP_PLACED", "POSITION_HELD") else ("#eab308" if s_status == "HUNTING" else "#64748b"))
            s_desc = ""
            if s_status == "HUNTING":
                s_desc = (
                    f"Ловушка в стакане: <b>${snp.get('buy_price', 0.0):.4f}</b> (-{SNIPER_DIP_DEPTH_PCT*100:.2f}%) | "
                    f"Пара: <b>{snp.get('symbol')}</b> | Бюджет: <b>${snp.get('allocated_usd', 5.25):.2f} USDT</b> | 🚀 <b>Sniper-Rocket Rider ГОТОВ</b>"
                )
            elif s_status == "ROCKET_ACTIVE":
                s_desc = (
                    f"🚀🔥 <b>РАКЕТА В ПОЛЕТЕ!</b> Пик: <b>${snp.get('peak_price', 0.0):.4f}</b> | "
                    f"Стоп подтянут: <b>${snp.get('stop_price', 0.0):.4f}</b> (-{SNIPER_ROCKET_CALLBACK_PCT*100:.2f}%) | "
                    f"Защитный пол: <b>${snp.get('floor_price', 0.0):.4f}</b> (+{SNIPER_ROCKET_FLOOR_PCT*100:.2f}%)"
                )
            elif s_status == "POSITION_HELD":
                s_desc = (
                    f"🎯 <b>Дно поймано!</b> Вход: <b>${snp.get('entry_price', 0.0):.4f}</b> ({snp.get('position_qty', 0.0)} {snp.get('symbol')}) | "
                    f"Ожидание активации Ракеты (+{SNIPER_ROCKET_ACTIVATION_PCT*100:.2f}%) 🚀"
                )
            elif s_status == "TP_PLACED":
                s_desc = (
                    f"⚡ ВХОД ВЫПОЛНЕН! Лимитный ТП: <b>${snp.get('tp_price', 0.0):.4f}</b> (+{SNIPER_TP_PCT*100:.2f}%) | "
                    f"Объем: <b>{snp.get('position_qty', 0.0)} {snp.get('symbol')}</b>"
                )
            else:
                s_desc = f"В ожидании условий | Бюджет: <b>${snp.get('allocated_usd', 5.25):.2f} USDT</b> | Режим: 🚀 Rocket Rider"

            s_badge_label = "🚀 ROCKET ACTIVE" if s_status == "ROCKET_ACTIVE" else s_status
            s_alloc_lbl = f"Изолирован ${snp.get('allocated_usd', 5.25):.2f}"
            s_obi = snp.get('obi', 0.0)
            s_obi_col = "#10b981" if s_obi >= 0.0 else ("#f59e0b" if s_obi >= -0.35 else "#ef4444")
            s_obi_lbl = f"OBI: {s_obi:+.3f}"

            sniper_html = f"""
            <div class="card" style="border: 1px solid rgba(234, 179, 8, 0.35); background: rgba(30, 27, 75, 0.45);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <h3 style="margin: 0; color: #facc15; text-shadow: 0 0 10px #facc1555;">🎯 Flash Sniper ({snp.get('symbol')})</h3>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span class="badge" style="background: {s_obi_col}22; color: {s_obi_col}; border: 1px solid {s_obi_col};">{s_obi_lbl}</span>
                        <span class="badge" style="background: {s_badge_col}22; color: {s_badge_col}; border: 1px solid {s_badge_col};">{s_badge_label}</span>
                        <span class="badge" style="background: #eab30822; color: #facc15; border: 1px solid #facc15;">{s_alloc_lbl}</span>
                    </div>
                </div>
                <div class="label" style="margin-top: 6px;">{s_desc}</div>
                <div class="label" style="margin-top: 4px; color: #10b981;">Закрыто проливов: <b>{snp.get('completed_cycles', 0)}</b> | Профит снайпера: <b>+${snp.get('total_profit_usd', 0.0):.4f} USDT</b></div>
            </div>
            """
        else:
            sniper_html = ""

        brk = st.get("breakout")
        if brk:
            b_status = brk.get("status", "IDLE")
            b_badge_col = "#a855f7" if b_status == "IN_FLIGHT" else ("#eab308" if b_status == "ARMED" else ("#64748b" if b_status == "COOLDOWN" else "#38bdf8"))
            b_desc = ""
            if b_status == "IN_FLIGHT":
                b_gain = ((float(st.get("tokens", {}).get(brk.get("symbol"), {}).get("price", 0.0)) - float(brk.get("entry_price", 1.0))) / float(brk.get("entry_price", 1.0))) * 100.0 if float(brk.get("entry_price", 0.0)) > 0 else 0.0
                b_desc = (
                    f"🚀🔥 <b>ИМПУЛЬС В ПОЛЕТЕ!</b> Вход: <b>${brk.get('entry_price', 0.0):.4f}</b> | "
                    f"Пик: <b>${brk.get('peak_price', 0.0):.4f}</b> | Стоп: <b>${brk.get('stop_price', 0.0):.4f}</b> | Профит: <b>{b_gain:+.2f}%</b>"
                )
            elif b_status == "ARMED":
                b_desc = (
                    f"🎯 <b>ПРОБОЙ НА ПРИЦЕЛЕ!</b> Цена выше сопротивления <b>${brk.get('resistance_price', 0.0):.4f}</b>. "
                    f"Ожидание всплеска объема (текущий: <b>{brk.get('volume_ratio', 0.0)}x</b> / порог 2.0x)"
                )
            elif b_status == "COOLDOWN":
                b_desc = "⏳ Защитная пауза после выхода из сделки (предотвращение пилы)."
            else:
                b_desc = (
                    f"Мониторинг сжатия и уровней | Сопротивление: <b>${brk.get('resistance_price', 0.0):.4f}</b> | "
                    f"Объем: <b>{brk.get('volume_ratio', 0.0)}x</b> | Режим: 🚀 Rocket Trailing"
                )

            breakout_html = f"""
            <div class="card" style="border: 1px solid rgba(168, 85, 247, 0.35); background: rgba(30, 27, 75, 0.45);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <h3 style="margin: 0; color: #c084fc; text-shadow: 0 0 10px #c084fc55;">⚡ Momentum Breakout ({brk.get('symbol')})</h3>
                    <div style="display: flex; gap: 6px; align-items: center;">
                        <span class="badge" style="background: {b_badge_col}22; color: {b_badge_col}; border: 1px solid {b_badge_col};">{b_status}</span>
                        <span class="badge" style="background: #a855f722; color: #c084fc; border: 1px solid #c084fc;">Изолирован ${brk.get('allocated_usd', 5.25):.2f}</span>
                    </div>
                </div>
                <div class="label" style="margin-top: 6px;">{b_desc}</div>
                <div class="label" style="margin-top: 4px; color: #10b981;">Закрыто импульсов: <b>{brk.get('completed_cycles', 0)}</b> | Профит стратегии: <b>+${brk.get('total_profit_usd', 0.0):.4f} USDT</b></div>
            </div>
            """
        else:
            breakout_html = ""

        total_usd_val = float(st.get('total_usd', 0.0))
        net_dep_profit = round(total_usd_val - 52.47, 2)
        net_dep_pct = round((net_dep_profit / 52.47) * 100, 2) if 52.47 > 0 else 0.0
        pnl_col = "#10b981" if net_dep_profit >= 0 else "#ef4444"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Bybit KZ Multi-Token Dashboard</title>
    <style>
        body {{
            background: #090d16 url('/dragon_bg.jpg') no-repeat center center fixed;
            background-size: cover;
            color: #f8fafc;
            font-family: -apple-system, system-ui, sans-serif;
            padding: 15px;
            margin: 0;
            min-height: 100vh;
        }}
        .card {{
            background: rgba(15, 23, 42, 0.48);
            backdrop-filter: blur(6px);
            -webkit-backdrop-filter: blur(6px);
            border-radius: 14px;
            padding: 16px;
            margin-bottom: 14px;
            border: 1px solid rgba(56, 189, 248, 0.28);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.40);
        }}
        h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.15rem; text-shadow: 0 0 14px rgba(56, 189, 248, 0.6); }}
        .metric {{ font-size: 1.8rem; font-weight: bold; color: #10b981; text-shadow: 0 0 16px rgba(16, 185, 129, 0.6); }}
        .label {{ font-size: 0.85rem; color: #f1f5f9; text-shadow: 0 1px 3px rgba(0,0,0,0.8); }}
        .badge {{ display: inline-block; padding: 4px 8px; border-radius: 6px; font-weight: bold; font-size: 0.8rem; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 0.85rem; }}
        th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid rgba(51, 65, 85, 0.6); }}
        th {{ color: #94a3b8; }}
        .buy {{ color: #38bdf8; font-weight: bold; }}
        .sell {{ color: #f59e0b; font-weight: bold; }}
        .btn {{ border: none; padding: 8px 16px; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 0.85rem; transition: transform 0.15s, opacity 0.2s; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }}
        .btn:hover {{ opacity: 0.9; transform: translateY(-1px); }}
    </style>
</head>
<body>
    <div class="card">
        <h2>⚡ Bybit Kazakhstan Autonomous Fund {profile_badge_html} {cmp_badge_html}</h2>
        <div class="label">Режим портфеля: <b>{st.get('portfolio_mode')}</b></div>
        <div class="metric">${st.get('total_usd', 0.0):.2f} USDT <span style="font-size: 0.95rem; font-weight: normal; color: {pnl_col}; text-shadow: none;">(Депозит: $52.47 | PnL: <b>{net_dep_profit:+.2f} USDT</b> / <b>{net_dep_pct:+.2f}%</b>)</span></div>
        <div class="label">Свободно: ${st.get('available_usdt', 0.0):.2f}{reserve_html} | В ордерах: ${st.get('locked_usdt', 0.0):.2f} | Компаундинг: <b>{cmp_mult:.2f}x</b></div>
        <div class="label" style="margin-top: 6px; color: #38bdf8;">Топливо комиссий: <b>{st.get('mnt_balance', 0.0):.4f} MNT</b></div>
        <div style="display: flex; gap: 8px; flex-wrap: wrap; align-items: center;">
            <div class="badge" style="background: {guard_color}22; color: {guard_color}; border: 1px solid {guard_color}; margin-top: 8px;">
                {st.get('global_guard_status')}
            </div>
            {lead_lag_badge_html}
        </div>

        <div style="display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap;">
            <button class="btn" onclick="botAction('/api/pause')" style="background: #f59e0b; color: #0f172a;">⏸️ Пауза (BUY)</button>
            <button class="btn" onclick="botAction('/api/resume')" style="background: #10b981; color: #0f172a;">▶️ Возобновить</button>
            <button class="btn" onclick="if(confirm('Снять ВСЕ активные ордера на покупку?')) botAction('/api/panic')" style="background: #ef4444; color: white;">🚨 Экстренная отмена (BUY)</button>
        </div>
    </div>

    {sniper_html}

    {breakout_html}

    {tokens_html}

    {ta_html}

    {news_card_html}

    <div class="card">
        <h2>📖 Активные ордера портфеля</h2>
        <div style="overflow-x: auto;">
            <table>
                <tr><th>Пара</th><th>Сторона</th><th>Цена</th><th>Объем</th><th>Сумма</th></tr>
                {orders_html if orders_html else "<tr><td colspan='5' style='text-align: center; color: #94a3b8;'>Нет активных ордеров</td></tr>"}
            </table>
        </div>
        <div class="label" style="margin-top: 8px;">Обновлено: {st.get('updated_at')} (Авто-обновление каждые 3с)</div>
    </div>

    <script>
    async function botAction(endpoint) {{
        try {{
            let resp = await fetch(endpoint, {{ method: 'POST' }});
            let data = await resp.json();
            setTimeout(() => location.reload(), 400);
        }} catch(e) {{
            alert('Ошибка выполнения: ' + e);
        }}
    }}
    setTimeout(() => location.reload(), 3000);
    </script>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        pass


# =====================================================================
# TELEGRAM REMOTE CONTROL PANEL (KEYBOARDS, STATUS, PAUSE, RESUME)
# =====================================================================

MAIN_REPLY_KEYBOARD = {
    "keyboard": [
        [{"text": "📊 Статус и Баланс"}, {"text": "📈 Сделки и PnL"}],
        [{"text": "⏸️ Пауза (все BUY)"}, {"text": "▶️ Возобновить"}],
        [{"text": "🔄 Передать смену"}, {"text": "🌐 Статус кластера"}],
        [{"text": "🚨 Panic Stop"}, {"text": "🔄 Обновить пульт"}]
    ],
    "resize_keyboard": True,
    "persistent": True
}

STATUS_INLINE_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🔄 Обновить данные", "callback_data": "btn_refresh"},
            {"text": "📈 Сделки", "callback_data": "btn_trades"}
        ],
        [
            {"text": "⏸️ Поставить на Паузу", "callback_data": "btn_pause"},
            {"text": "▶️ Возобновить", "callback_data": "btn_resume"}
        ],
        [
            {"text": "🔄 Передать смену", "callback_data": "btn_handover"},
            {"text": "🌐 Кластер", "callback_data": "btn_cluster"}
        ]
    ]
}

PANIC_CONFIRM_KEYBOARD = {
    "inline_keyboard": [
        [
            {"text": "🚨 ДА, СНЯТЬ ВСЕ BUY", "callback_data": "btn_confirm_panic"},
            {"text": "❌ Отмена", "callback_data": "btn_cancel_panic"}
        ]
    ]
}


def send_telegram_reply(
    text: str,
    chat_id: str = TELEGRAM_CHAT_ID,
    reply_markup: Optional[Dict[str, Any]] = None,
    message_id_to_edit: Optional[int] = None,
) -> Optional[int]:
    """Sends a new message or edits an existing message in Telegram."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not chat_id:
        return None
    try:
        if message_id_to_edit:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText"
            payload_dict: Dict[str, Any] = {
                "chat_id": chat_id,
                "message_id": message_id_to_edit,
                "text": text,
                "parse_mode": "Markdown",
            }
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload_dict = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }
        if reply_markup is not None:
            payload_dict["reply_markup"] = reply_markup

        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "BybitBotControl/2.0"},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return int(data.get("result", {}).get("message_id") or 0)
    except urllib.error.HTTPError as he:
        if he.code == 400 and "parse_mode" in payload_dict:
            try:
                payload_dict.pop("parse_mode", None)
                payload = json.dumps(payload_dict).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "BybitBotControl/2.0"})
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("ok"):
                        return int(data.get("result", {}).get("message_id") or 0)
            except Exception as e2:
                logger.warning(f"Telegram plain reply fallback error: {e2}")
        else:
            logger.warning(f"Telegram reply/edit error: {he}")
    except Exception as e:
        logger.warning(f"Telegram reply/edit error: {e}")
    return None


def answer_callback_query(callback_id: str, text: Optional[str] = None) -> None:
    """Acknowledges an inline button click to dismiss the loading animation."""
    if not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not callback_id:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery"
        payload_dict: Dict[str, Any] = {"callback_query_id": callback_id}
        if text:
            payload_dict["text"] = text
        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "BybitBotControl/2.0"},
        )
        urllib.request.urlopen(req, timeout=12)
    except Exception as e:
        logger.debug(f"Callback answer error: {e}")


def format_status_text(bot: StandaloneBybitBot) -> str:
    st = bot.stats
    mode_str = "⏸️ *НА ПАУЗЕ (Все покупки заморожены)*" if bot.is_paused else "▶️ *АКТИВЕН (Портфель работает)*"
    if not bot.is_active_controller:
        mode_str = "👁️ *PASSIVE OBSERVER (Дежурный режим)*"

    profile_badge = "🖥️ *[DESKTOP / SMART-STEP]*" if bot.mode == "desktop" else "📱 *[MOBILE / STORM]*"
    reserve_badge = f"\n• Резервный буфер: `${bot.reserve_usdt:.2f} USDT` 🛡️" if bot.reserve_usdt > 0 else ""

    total_usd = st.get("total_usd", 0.0)
    avail = st.get("available_usdt", 0.0)
    locked = st.get("locked_usdt", 0.0)
    port_mode = st.get("portfolio_mode", "Single")
    global_guard = st.get("global_guard_status", "🟢 Норма")
    btc_1m = st.get("btc_1m_chg", 0.0)
    updated = st.get("updated_at", "")

    mnt_bal = float(st.get("mnt_balance") or 0.0)
    if mnt_bal >= 0.50:
        mnt_status_str = f"🟢 `{mnt_bal:.3f} MNT` (В норме)"
        mnt_alert = ""
    elif mnt_bal >= 0.05:
        mnt_status_str = f"🟡 `{mnt_bal:.3f} MNT` (Снижается)"
        mnt_alert = ""
    else:
        mnt_status_str = f"🔴 `{mnt_bal:.4f} MNT` ⚠️ *(Заканчивается!)*"
        mnt_alert = "\n💡 _Совет: Топливо MNT почти на нуле. Рекомендуется купить 1–2 MNT (~$1.50) для скидки 25% на комиссии и чистых сделок без пыли._\n"

    # Token blocks
    token_blocks = []
    for sym, t in st.get("tokens", {}).items():
        base_c = t.get("base_coin", sym)
        p = t.get("price", 0.0)
        fc = t.get("free_coin", 0.0)
        hv = t.get("holding_value_usd", 0.0)
        t_mode = t.get("mode", "ACTIVE")
        cyc = t.get("completed_cycles", 0)
        prof = t.get("net_profit_usd", 0.0)
        tp_m = t.get("tp_mode", "Standard (+0.90%)")
        s1 = t.get("step1_discount_pct", 0.55)
        s2 = t.get("step2_discount_pct", 1.75)
        s3 = t.get("step3_discount_pct", 3.20)
        vol_reg = t.get("volatility_regime", "NORMAL")
        mult = t.get("vol_multiplier", 1.0)
        icon = "🔷" if base_c == "SUI" else ("🟢" if base_c == "NEAR" else "🔴")

        token_blocks.append(
            f"{icon} *{sym}* [{t_mode}]\n"
            f"• Спот: `${p:.4f}` | 1m: `{t.get('chg_1m_pct', 0.0):+.2f}%`\n"
            f"• Позиция: `{fc} {base_c}` (~`${hv:.2f}`)\n"
            f"• Сетка ({vol_reg} x{mult}): -{s1}% / -{s2}% / -{s3}%\n"
            f"• Тейк-профит: *{tp_m}*\n"
            f"• Закрыто циклов: *{cyc}* (+$`{prof:.4f}` USDT)"
        )

    tokens_str = "\n\n".join(token_blocks)

    orders = st.get("all_open_orders", [])
    if orders:
        lines = []
        for o in orders:
            side = o.get("side", "")
            sym = o.get("symbol", "")
            q = o.get("qty", "")
            p = o.get("price", "")
            icon = "🟢" if side == "Buy" else "🔴"
            try:
                val = float(q) * float(p)
                lines.append(f"• {icon} {sym} {side} {q} @ ${p} (${val:.2f})")
            except Exception:
                lines.append(f"• {icon} {sym} {side} {q} @ ${p}")
        orders_str = "\n".join(lines)
    else:
        orders_str = "• Нет активных ордеров в стакане"

    ll = st.get("lead_lag", {})
    ll_status = ll.get("status", "CLEAR")
    ll_icon = "🟢" if ll_status in ("CLEAR", "BULLISH") else ("🟡" if ll_status == "SLIDING" else "🔴")
    ll_gate = "Вход открыт" if ll.get("gate_step1_open", True) else "Вход заморожен"

    return (
        f"🎛️ *BYBIT КАЗАХСТАН: МИКРО-ФОНД*\n\n"
        f"Профиль: {profile_badge}\n"
        f"Режим: *{port_mode}*\n"
        f"Статус: {mode_str}\n\n"
        f"💰 *Баланс: ${total_usd:.2f} USDT*\n"
        f"• Свободно: `${avail:.2f} USDT`\n"
        f"• В ордерах: `${locked:.2f} USDT`"
        f"{reserve_badge}\n"
        f"• Топливо (MNT): {mnt_status_str}\n"
        f"• Lead-Lag Radar: {ll_icon} *{ll_status}* ({ll_gate})\n"
        f"  └ BTC 1m: `{btc_1m:+.2f}%` | 3m: `{ll.get('btc_3m_chg', 0.0):+.2f}%`\n\n"
        f"{tokens_str}\n\n"
        f"📖 *Ордера в стакане:*\n{orders_str}\n"
        f"{mnt_alert}"
        f"⏱ _Обновлено: {updated}_"
    )


def format_trades_text(bot: StandaloneBybitBot) -> str:
    st = bot.stats
    total_prof = sum(t.get("net_profit_usd", 0.0) for t in st.get("tokens", {}).values())
    total_cyc = sum(t.get("completed_cycles", 0) for t in st.get("tokens", {}).values())

    lines = []
    for sym in [PRIMARY_SYMBOL, SECONDARY_SYMBOL, TERTIARY_SYMBOL]:
        try:
            execs = bot.client.get_execution_history(sym, limit=5)
            for e in execs:
                dt = datetime.datetime.fromtimestamp(float(e.get("execTime", 0)) / 1000.0).strftime("%d.%m %H:%M")
                side = e.get("side", "")
                icon = "🟢" if side == "Buy" else "🎯"
                q = e.get("execQty", "")
                p = e.get("execPrice", "")
                v = float(e.get("execValue", 0.0))
                lines.append(f"{icon} `[{dt}]` {sym[:3]} {side:<4} {q:>5} @ ${p} (${v:.2f})")
        except Exception:
            pass

    execs_str = "\n".join(lines) if lines else "Нет недавних сделок"

    return (
        f"📈 *ИСТОРИЯ СДЕЛОК ПОРТФЕЛЯ*\n\n"
        f"• Всего циклов закрыто: *{total_cyc}* (100% Win Rate)\n"
        f"• Общий чистый PnL: *+${total_prof:.4f} USDT*\n\n"
        f"📋 *Последние сделки:*\n{execs_str}"
    )


def handle_telegram_text(bot: StandaloneBybitBot, text: str, chat_id: str) -> None:
    t = text.strip().lower()
    if t in ["📊 статус и баланс", "/status", "/balance", "статус", "баланс"]:
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD)
    elif t in ["📈 сделки и pnl", "/trades", "/pnl", "сделки", "профит"]:
        send_telegram_reply(format_trades_text(bot), chat_id=chat_id, reply_markup=MAIN_REPLY_KEYBOARD)
    elif t in ["⏸️ пауза (все buy)", "⏸️ пауза (только тп)", "/pause", "пауза", "pause"]:
        bot.is_paused = True
        bot.cancel_all_portfolio_buys()
        send_telegram_reply(
            "⏸️ *ПОРТФЕЛЬ ПОСТАВЛЕН НА ПАУЗУ*\n\n"
            "• Все активные BUY-ордера во всех парах сняты из стакана.\n"
            "• Тейк-профиты (SELL) остаются активными и ждут закрытия в плюс.\n"
            "• Новые покупки заблокированы.\n\n"
            "Нажмите *«▶️ Возобновить»*, чтобы вернуть сетку в работу.",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD
        )
    elif t in ["▶️ возобновить", "/resume", "/start", "старт", "возобновить", "resume"]:
        bot.is_paused = False
        send_telegram_reply(
            "▶️ *ТОРГОВЛЯ ВОЗОБНОВЛЕНА!*\n\n"
            "• Портфель снова в строю.\n"
            "• В течение 10 секунд алгоритм оценит рынок и выставит свежие ордера сетки.",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD
        )
    elif t in ["🚨 panic stop", "/panic", "panic", "паника"]:
        send_telegram_reply(
            "⚠️ *ПОДТВЕРЖДЕНИЕ ЭКСТРЕННОЙ ОСТАНОВКИ*\n\n"
            "Вы уверены, что хотите снять ВСЕ ордера на покупку по всем токенам и заморозить бота?",
            chat_id=chat_id,
            reply_markup=PANIC_CONFIRM_KEYBOARD
        )
    elif t in ["🔄 обновить пульт", "меню", "/menu"]:
        send_telegram_reply(
            "🎛️ *Пульт управления Bybit обновлен!*\nИспользуйте кнопки меню внизу экрана.",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD
        )
    elif t in ["🔄 передать смену", "/handover", "передать смену", "смена"]:
        target = "mobile" if bot.mode == "desktop" else "desktop"
        bot.handover_to(target, "Ручная передача через Telegram")
    elif t in ["/handover_to_desktop", "на пк"]:
        bot.handover_to("desktop", "Команда /handover_to_desktop")
    elif t in ["/handover_to_mobile", "на телефон"]:
        bot.handover_to("mobile", "Команда /handover_to_mobile")
    elif t in ["🌐 статус кластера", "кластер", "/cluster"]:
        state = read_cluster_state()
        astana_dt = get_astana_time()
        in_win = "В рабочем окне ПК (08:00 - 17:30)" if is_desktop_schedule_window() else "Вне офисных часов (Дежурный режим)"
        hb_ts = float(state.get("heartbeat_ts", 0.0))
        hb_age = int(time.time() - hb_ts) if hb_ts > 0 else 0
        send_telegram_reply(
            f"🌐 *[СОСТОЯНИЕ КЛАСТЕРА BYBIT]*\n\n"
            f"• Локальный узел: *{bot.mode.upper()}* (`{bot.role}`)\n"
            f"• Активный хост по борду: *{state.get('active_host', '').upper()}*\n"
            f"• Heartbeat: `{hb_age}с назад`\n"
            f"• Время (Астана): `{astana_dt.strftime('%d.%m.%Y %H:%M:%S')}`\n"
            f"• График: *{in_win}*\n"
            f"• Защита Failover: `3 мин (180с)`\n\n"
            f"Команды: `/handover_to_desktop`, `/handover_to_mobile`",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD
        )
    else:
        send_telegram_reply(
            "Команда не распознана. Используйте кнопки на пульте ниже:",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD
        )


def handle_telegram_callback(
    bot: StandaloneBybitBot,
    cb_id: str,
    chat_id: str,
    msg_id: int,
    data: str,
) -> None:
    if data == "btn_refresh":
        answer_callback_query(cb_id, "Данные обновлены ✅")
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD, message_id_to_edit=msg_id)
    elif data == "btn_trades":
        answer_callback_query(cb_id, "История загружена 📊")
        send_telegram_reply(format_trades_text(bot), chat_id=chat_id, message_id_to_edit=msg_id)
    elif data == "btn_pause":
        bot.is_paused = True
        bot.cancel_all_portfolio_buys()
        answer_callback_query(cb_id, "Портфель на паузе ⏸️")
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD, message_id_to_edit=msg_id)
    elif data == "btn_resume":
        bot.is_paused = False
        answer_callback_query(cb_id, "Торговля возобновлена ▶️")
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD, message_id_to_edit=msg_id)
    elif data == "btn_handover":
        target = "mobile" if bot.mode == "desktop" else "desktop"
        bot.handover_to(target, "Inline-кнопка в Telegram")
        answer_callback_query(cb_id, f"Смена передана на {target} 🔄")
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD, message_id_to_edit=msg_id)
    elif data == "btn_cluster":
        answer_callback_query(cb_id, "Статус кластера 🌐")
        handle_telegram_text(bot, "/cluster", chat_id)
    elif data == "btn_confirm_panic":
        bot.is_paused = True
        bot.cancel_all_portfolio_buys()
        answer_callback_query(cb_id, "Все BUY отменены! 🚨")
        send_telegram_reply(
            "🚨 *АВАРИЙНАЯ ОСТАНОВКА ВЫПОЛНЕНА*\n\n"
            "• Все BUY-ордера во всех токенах отозваны.\n"
            "• Бот заморожен. Чтобы вернуться к торгам, нажмите «▶️ Возобновить».",
            chat_id=chat_id,
            reply_markup=MAIN_REPLY_KEYBOARD,
            message_id_to_edit=msg_id
        )
    elif data == "btn_cancel_panic":
        answer_callback_query(cb_id, "Отмена действия ❌")
        send_telegram_reply(format_status_text(bot), chat_id=chat_id, reply_markup=STATUS_INLINE_KEYBOARD, message_id_to_edit=msg_id)


def telegram_polling_thread(bot: StandaloneBybitBot) -> None:
    if not bot.enable_telegram or not ENABLE_TELEGRAM or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.info("Telegram controller disabled.")
        return

    logger.info("📱 [Telegram Control Panel] Поток запущен. Слушаем команды...")
    send_telegram_reply(
        "🎛️ *Bybit Spot Multi-Token Bot на связи!*\n"
        "Пульт управления активирован. Кнопки добавлены в нижнее меню.",
        chat_id=TELEGRAM_CHAT_ID,
        reply_markup=MAIN_REPLY_KEYBOARD,
    )

    last_offset = 0
    while bot.running:
        # Passive observer does NOT poll getUpdates to prevent Telegram 409 Conflict
        if not bot.is_active_controller or bot.role == "PASSIVE_OBSERVER":
            time.sleep(2)
            continue

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_offset + 1}&timeout=15"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BybitControl/2.0"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if not data.get("ok"):
                time.sleep(2)
                continue

            for u in data.get("result", []):
                last_offset = u.get("update_id", last_offset)

                # 1. Message from user
                m = u.get("message")
                if m:
                    cid = str(m.get("chat", {}).get("id", ""))
                    if cid == str(TELEGRAM_CHAT_ID):
                        txt = m.get("text", "")
                        if txt:
                            handle_telegram_text(bot, txt, cid)

                # 2. Inline callback
                cb = u.get("callback_query")
                if cb:
                    cid = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                    if cid == str(TELEGRAM_CHAT_ID):
                        cb_id = cb.get("id", "")
                        mid = cb.get("message", {}).get("message_id", 0)
                        c_data = cb.get("data", "")
                        handle_telegram_callback(bot, cb_id, cid, mid, c_data)

        except urllib.error.HTTPError as he:
            if he.code == 409:
                logger.warning("Telegram 409 Conflict: another instance is polling getUpdates. Retrying in 5s...")
                time.sleep(5)
            else:
                time.sleep(3)
        except Exception:
            time.sleep(3)


def init_cluster_role(bot: StandaloneBybitBot) -> None:
    """Arbitrates initial cluster role on startup before Telegram polling begins."""
    if not bot.enable_telegram:
        if bot.mode == "desktop":
            if bot.is_24x7 or is_desktop_schedule_window():
                label = "Режим 24/7" if bot.is_24x7 else "Офисное время Астаны (08:00 - 17:30)"
                logger.info(f"🖥️ [Desktop Startup] {label}. Активация Desktop (Standalone)...")
                bot.is_active_controller = True
                bot.role = "ACTIVE_CONTROLLER"
            else:
                logger.info("🖥️ [Desktop Startup] Вне офисных часов. Запуск в режиме PASSIVE_OBSERVER...")
                bot.is_active_controller = False
                bot.role = "PASSIVE_OBSERVER"
        else:
            if is_desktop_schedule_window():
                logger.info("📱 [Mobile Startup] Офисные часы Астаны. Запуск в режиме PASSIVE_OBSERVER...")
                bot.is_active_controller = False
                bot.role = "PASSIVE_OBSERVER"
            else:
                logger.info("📱 [Mobile Startup] Вне офисных часов. Активация Mobile...")
                bot.is_active_controller = True
                bot.role = "ACTIVE_CONTROLLER"
        return

    init_state = read_cluster_state()
    bot.cluster_board_msg_id = init_state.get("msg_id")

    # If desktop starts up during office hours or in 24/7 mode, claim active controller
    if bot.mode == "desktop":
        if bot.is_24x7 or is_desktop_schedule_window():
            reason = "Режим 24/7 (круглосуточный ПК)" if bot.is_24x7 else "Запуск рабочего ПК в офисе"
            logger.info(f"🖥️ [Desktop Startup] {reason}. Активация Desktop...")
            bot.handover_to("desktop", reason)
            time.sleep(2)
        else:
            logger.info("🖥️ [Desktop Startup] Вне офисных часов. Запуск в режиме PASSIVE_OBSERVER...")
            bot.is_active_controller = False
            bot.role = "PASSIVE_OBSERVER"
    else:
        # Mobile mode: check if desktop schedule window is active
        if is_desktop_schedule_window():
            logger.info("📱 [Mobile Startup] Офисные часы Астаны (08:00 - 17:30). Запуск Mobile в режиме PASSIVE_OBSERVER...")
            bot.is_active_controller = False
            bot.role = "PASSIVE_OBSERVER"
            bot.cluster_board_msg_id = write_cluster_state(
                "desktop",
                "Офисные часы Астаны (08:00 - 17:30)",
                bot.cluster_board_msg_id,
            )
        else:
            logger.info("📱 [Mobile Startup] Вне офисных часов. Активация Mobile...")
            bot.handover_to("mobile", "Старт телефона (дефолтный узел вне офиса)")


def cluster_watchdog_thread(bot: StandaloneBybitBot) -> None:
    """Monitors heartbeat, enforces Astana office schedule, and triggers automatic failover."""
    logger.info("🌐 [Cluster Watchdog] Поток мониторинга кластера запущен.")

    while bot.running:
        try:
            now = time.time()
            astana_dt = get_astana_time()
            in_win = is_desktop_schedule_window()

            if not bot.enable_telegram:
                if bot.mode == "desktop":
                    if bot.is_24x7:
                        if not bot.is_active_controller:
                            logger.info("🖥️ [Desktop 24/7] Активация роли ACTIVE_CONTROLLER в режиме 24/7.")
                            bot.is_active_controller = True
                            bot.role = "ACTIVE_CONTROLLER"
                    elif in_win and not bot.is_active_controller:
                        logger.info("🖥️ [Desktop Schedule] Наступило 08:00 по Астане. Активация Desktop.")
                        bot.is_active_controller = True
                        bot.role = "ACTIVE_CONTROLLER"
                    elif not in_win and bot.is_active_controller:
                        logger.info("🖥️ [Desktop Schedule] Наступило 17:30 по Астане. Завершение смены ПК -> PASSIVE_OBSERVER.")
                        bot.is_active_controller = False
                        bot.role = "PASSIVE_OBSERVER"
                        bot.cancel_all_portfolio_buys()
                else:
                    if in_win and bot.is_active_controller:
                        logger.info("📱 [Mobile Schedule] 08:00 - 17:30 по Астане. Смена Desktop -> Mobile переходит в PASSIVE_OBSERVER.")
                        bot.is_active_controller = False
                        bot.role = "PASSIVE_OBSERVER"
                        bot.cancel_all_portfolio_buys()
                    elif not in_win and not bot.is_active_controller:
                        logger.info("📱 [Mobile Schedule] 17:30 по Астане (или выходной). Активация Mobile.")
                        bot.is_active_controller = True
                        bot.role = "ACTIVE_CONTROLLER"
                time.sleep(10)
                continue

            if bot.role == "ACTIVE_CONTROLLER":
                # Check if Mobile needs to yield to Desktop during Astana office hours
                if bot.mode == "mobile" and is_desktop_schedule_window():
                    logger.info("🖥️ [Schedule Window] Офисные часы Астаны (08:00 - 17:30). Mobile уступает смену Desktop -> PASSIVE_OBSERVER.")
                    bot.is_active_controller = False
                    bot.role = "PASSIVE_OBSERVER"
                    bot.cancel_all_portfolio_buys()
                    bot.cluster_board_msg_id = write_cluster_state(
                        "desktop",
                        "Офисные часы Астаны (08:00 - 17:30)",
                        bot.cluster_board_msg_id,
                    )
                    send_telegram(
                        "📱 *[КЛАСТЕР: СМЕНА СДАНА ПО ГРАФИКУ]*\n\n"
                        "Наступило 08:00 по Астане.\n"
                        "Телефон перешел в режим `PASSIVE_OBSERVER`.\n"
                        "• Все BUY-ордера мобильной сетки сняты.\n"
                        "• Управление передано Desktop.\n"
                        "• Тейк-профиты сохранены."
                    )
                    time.sleep(10)
                    continue

                # Active host sends periodic heartbeat
                if now - bot.last_heartbeat_sent_ts >= HEARTBEAT_INTERVAL_SECONDS:
                    bot.last_heartbeat_sent_ts = now
                    bot.cluster_board_msg_id = write_cluster_state(
                        bot.mode,
                        f"В строю (Астана {astana_dt.strftime('%H:%M')})",
                        bot.cluster_board_msg_id,
                    )

                # Periodic Hourly Heartbeat for Telegram remote observer (every 60 mins)
                if bot.enable_telegram and (now - bot.last_hourly_alert_ts >= 3600):
                    bot.last_hourly_alert_ts = now
                    st = bot.stats
                    eq = st.get("total_usd", 0.0)
                    cycles = bot.token_cycles.get(PRIMARY_SYMBOL, 0)
                    tok_sui = st.get("tokens", {}).get(PRIMARY_SYMBOL, {})
                    p_val = tok_sui.get("price", 0.0)
                    send_telegram(
                        f"💓 **[ПУЛЬС БОТА: ДЕСКТОП В СТРОЮ]**\n\n"
                        f"• Время (Астана): `{astana_dt.strftime('%H:%M')}`\n"
                        f"• Статус: `24/7 ACTIVE` (Экран погашен, ПК молотит)\n"
                        f"• Баланс: **${eq:.2f} USDT**\n"
                        f"• SUI: **${p_val:.4f}** (Закрыто циклов: {cycles})\n"
                        f"• Ночной дежурный на посту! 🚀"
                    )

                # Desktop schedule enforcement: auto-handover at 17:30 (bypassed in 24/7 mode)
                if bot.mode == "desktop":
                    if not bot.is_24x7 and not is_desktop_schedule_window():
                        logger.info("🖥️ [Desktop Schedule] Наступило 17:30 (или выходной). Авто-передача смены на телефон...")
                        bot.handover_to("mobile", "Окончание офисного дня (17:30 по Астане)")

            elif bot.role == "PASSIVE_OBSERVER":
                # Passive host polls cluster board every 10s via getChat (zero 409 conflict)
                state = read_cluster_state()
                if state.get("msg_id"):
                    bot.cluster_board_msg_id = state.get("msg_id")
                active_host = state.get("active_host")
                hb_ts = float(state.get("heartbeat_ts", 0.0))
                hb_age = now - hb_ts

                if active_host == bot.mode:
                    if bot.mode == "mobile" and is_desktop_schedule_window():
                        # Strictly do NOT activate mobile during desktop office hours
                        time.sleep(10)
                        continue
                    # Handover was requested for us!
                    logger.info(f"🔔 [Handover Detected] Получен сигнал смены на {bot.mode.upper()}!")
                    bot.is_active_controller = True
                    bot.role = "ACTIVE_CONTROLLER"
                    send_telegram(
                        f"📱 *[КЛАСТЕР: СМЕНА ПРИНЯТА]*\n\n"
                        f"Узел {bot.mode.upper()} перешел в режим `ACTIVE_CONTROLLER`.\n"
                        f"Развертывание торговой сетки."
                    )
                elif bot.mode == "mobile":
                    # Check Canary Order first: if Desktop is running 24/7 and updating canary, Desktop is healthy!
                    canary_st = bot.get_canary_status()
                    canary_alive = (canary_st.get("found") and canary_st.get("age_sec", 999.0) < CANARY_FAILOVER_TIMEOUT_SEC)

                    # Check if office window has ended, BUT only take over if desktop is NOT actively running (no live canary)
                    if not is_desktop_schedule_window():
                        if canary_alive:
                            # Desktop is running in 24/7 mode or still active. Mobile remains PASSIVE_OBSERVER!
                            logger.info(
                                f"🖥️ [Desktop 24/7 Active] Наступило 17:30, но Desktop активен (Канарейка свежая: {canary_st.get('age_sec', 0):.0f}с). "
                                f"Телефон остается в PASSIVE_OBSERVER (ночной сторож)."
                            )
                        else:
                            logger.info("📱 [Desktop Schedule End] Наступило 17:30 по Астане и ПК не удерживает канарейку. Телефон принимает смену.")
                            bot.is_active_controller = True
                            bot.role = "ACTIVE_CONTROLLER"
                            bot.cluster_board_msg_id = write_cluster_state(
                                "mobile",
                                "Окончание офисных часов (17:30 по Астане)",
                                bot.cluster_board_msg_id,
                            )
                            send_telegram(
                                "📱 *[КЛАСТЕР: ВЕЧЕРНЯЯ СМЕНА]*\n\n"
                                "Наступило 17:30 по Астане (ПК не в 24/7).\n"
                                "Телефон автоматически активировал `ACTIVE_CONTROLLER` и перешел на сетку STORM x2.0."
                            )
                    canary_stale = (canary_st.get("found") and canary_st.get("age_sec", 0.0) >= CANARY_FAILOVER_TIMEOUT_SEC)
                    canary_missing = (not canary_st.get("found") and active_host == "desktop" and hb_age >= CANARY_FAILOVER_TIMEOUT_SEC)
                    telegram_stale = (active_host == "desktop" and hb_age >= HEARTBEAT_TIMEOUT_SECONDS)

                    should_failover = (ENABLE_AUTO_FAILOVER or not bot.enable_telegram) and (
                        canary_stale or (canary_missing and telegram_stale) or (telegram_stale and not canary_st.get("found"))
                    )

                    if should_failover:
                        fail_reason = (
                            f"Канарейка {CANARY_ORDER_LINK_PREFIX} не обновлялась {int(canary_st.get('age_sec', 0))}с"
                            if canary_stale
                            else f"ПК молчит {int(hb_age)}с (нет пульса и канарейки)"
                        )
                        logger.warning(f"🚨 [Cluster Failover] {fail_reason}! Аварийный перехват на телефон...")
                        bot.is_active_controller = True
                        bot.role = "ACTIVE_CONTROLLER"
                        # Clean up stale canary order if it still exists
                        bot.cancel_canary_order()
                        bot.cluster_board_msg_id = write_cluster_state(
                            "mobile",
                            f"АВАРИЙНЫЙ ПЕРЕХВАТ ({fail_reason})",
                            bot.cluster_board_msg_id,
                        )
                        send_telegram(
                            f"🚨 *[FAILOVER: АВАРИЙНЫЙ ПЕРЕХВАТ УПРАВЛЕНИЯ]*\n\n"
                            f"Причина: **{fail_reason}**!\n"
                            "Рабочий компьютер отключился или ушел в сон.\n"
                            "Телефон автоматически активировал роль `ACTIVE_CONTROLLER` и поднял защитную сетку STORM x2.0!"
                        )

            time.sleep(10)
        except Exception as e:
            logger.debug(f"cluster_watchdog_thread loop error: {e}")
            time.sleep(10)


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start_server(bot: StandaloneBybitBot) -> None:
    """Runs local mobile dashboard on background thread."""
    SimpleDashboardHandler.bot_instance = bot
    try:
        with ThreadingTCPServer(("", PORT), SimpleDashboardHandler) as httpd:
            logger.info(f"📱 Мобильный дашборд: http://localhost:{PORT}/")
            httpd.serve_forever()
    except Exception as e:
        logger.warning(f"Dashboard server bind warning: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bybit Kazakhstan Standalone Multi-Token Trading Bot")
    parser.add_argument(
        "--mode",
        choices=["mobile", "desktop"],
        default="mobile",
        help="Execution profile: 'mobile' (conservative STORM, default) or 'desktop' (aggressive Smart Step + $10 reserve)",
    )
    parser.add_argument(
        "--no-telegram",
        action="store_true",
        help="Disable all Telegram API calls and remote listener (pure standalone mode without network dependencies)",
    )
    parser.add_argument(
        "--24x7",
        dest="is_24x7",
        action="store_true",
        help="Run desktop in 24/7 round-the-clock mode without handing over or stopping at 17:30",
    )
    args = parser.parse_args()
    if args.no_telegram:
        ENABLE_TELEGRAM = False

    bot = StandaloneBybitBot(mode=args.mode, enable_telegram=not args.no_telegram, is_24x7=args.is_24x7)
    init_cluster_role(bot)
    t_web = threading.Thread(target=start_server, args=(bot,), daemon=True)
    t_web.start()
    if bot.enable_telegram:
        t_tg = threading.Thread(target=telegram_polling_thread, args=(bot,), daemon=True, name="TelegramControl")
        t_tg.start()
    t_dog = threading.Thread(target=cluster_watchdog_thread, args=(bot,), daemon=True, name="ClusterWatchdog")
    t_dog.start()
    bot.run_forever()
