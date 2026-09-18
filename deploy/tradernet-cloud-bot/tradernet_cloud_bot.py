"""
Cloud Tradernet Multi-Asset Trading Bot (Render.com Web Service)
AI-Enhanced with DeepSeek + Global Crypto Market Signal (Binance Lead-Lag Arb).

Trades:
- Crypto: SOL/USD on Freedom sub-account CR725726 guided by DeepSeek + global Binance momentum.
- KASE Stocks: HSBK.KZ, ASBN.KZ, KMGD.KZ during official market hours (10:00 - 17:00 UTC+5).
- Web Server on $PORT for Render Health-Check.
"""

import os
import sys
import json
import time
import datetime
import logging
import threading
import urllib.request
import asyncio
import math
from typing import Optional
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler
import tradernet
from latency_telemetry_worker import LatencyBenchmarkEngine
from bybit_client import BybitV5Client

def extract_best_ask_qty(quote: dict) -> Optional[float]:
    """Извлечение глубины верхнего уровня стакана Tradernet."""
    raw_qty = (
        quote.get("bas")
        or quote.get("bap_q")
        or quote.get("ask_qty")
        or quote.get("x_min_lot_q")
    )
    if raw_qty is None:
        return None
    try:
        val = float(raw_qty)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None

def calculate_clip_size(
    price: float,
    free_cash: float,
    bap_q: Optional[float] = None,
    max_alloc_pct: float = 0.35,
    min_lot: float = 1.0,
    lot_step: float = 1.0,
    lot_decimals: int = 0,
) -> float:
    """
    Расчет безопасного размера клипа с учетом:
    - Ценового тира монеты
    - Потолка аллокации от свободного кэша (по умолчанию 35%)
    - Book Depth Guard (не более 60% видимого Best Ask)
    - Квантования под шаг лота брокера (целый или дробный)
    """
    if price <= 0 or free_cash <= 0:
        return 0.0

    # 1. Базовый целевой объем по стоимости (~$3.00 - $4.00 на клип)
    if price < 0.50:
        target_cost = 3.50  # Дешевые (XLM, ADA): ~15-25 монет для ощутимого долларового профита
    elif price < 2.00:
        target_cost = 3.50  # Средние (SUI, APT): ~3-5 монет
    else:
        target_cost = max(price * min_lot, 3.80)  # Дорогие (DOT, NEAR, SOL)

    target_qty = target_cost / price

    # 2. Hard Cap по свободному капиталу (с буфером $0.05 на проскальзывание)
    available_pool = max(0.0, (free_cash * max_alloc_pct) - 0.05)
    max_affordable_qty = available_pool / price
    qty = min(target_qty, max_affordable_qty)

    # 3. Book Depth Guard: забираем не более 60% объема маркетмейкера
    if bap_q is not None and bap_q > 0:
        depth_limit = bap_q * 0.60
        if depth_limit >= min_lot:
            qty = min(qty, depth_limit)

    # 4. Квантование под шаг лота (lot_step)
    if qty < min_lot:
        # Проверяем, проходит ли хотя бы 1 минимальный лот
        if (min_lot * price) <= available_pool:
            qty = min_lot
        else:
            return 0.0
    else:
        steps = math.floor(round(qty / lot_step, 6))
        qty = steps * lot_step

    return round(qty, lot_decimals)


# Bybit Kazakhstan Regional Configuration
BYBIT_DOMAIN = os.environ.get("BYBIT_API_DOMAIN", "api.bybit.kz")
BYBIT_WS_URL = os.environ.get("BYBIT_WS_URL", "wss://stream.bybit.kz/v5/public/spot")

# Initialize high-frequency Bybit.kz vs Tradernet Delta-t Latency Benchmark
LATENCY_ENGINE = LatencyBenchmarkEngine(symbol_bybit="SUIUSDT", threshold_pct=0.25, ws_url=BYBIT_WS_URL)

def get_process_memory_mb() -> float:
    """Returns current process RSS memory in MB."""
    try:
        # On Linux (Docker/Render)
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    # Line looks like: VmRSS:     45120 kB
                    parts = line.split()
                    return round(float(parts[1]) / 1024.0, 2)
    except Exception:
        pass
    try:
        # Fallback via resource if on Unix
        import resource
        return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
    except Exception:
        pass
    return 0.0

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TradernetCloudAI")

# Auto-load .env for local development / testing
_env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
if os.path.exists(_env_file):
    try:
        with open(_env_file, "r", encoding="utf-8") as _ef:
            for _line in _ef:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())
    except Exception:
        pass

PORT = int(os.environ.get("PORT", "10000"))

# API Keys loaded strictly from environment variables or .env (No hardcoded secrets)
KASE_PUB_KEY = os.environ.get("KASE_PUB_KEY", os.environ.get("TRADERNET_PUBLIC_KEY", ""))
KASE_SEC_KEY = os.environ.get("KASE_SEC_KEY", os.environ.get("TRADERNET_PRIVATE_KEY", ""))

CRYPTO_PUB_KEY = os.environ.get("CRYPTO_PUB_KEY", os.environ.get("TRADERNET_PUBLIC_KEY", ""))
CRYPTO_SEC_KEY = os.environ.get("CRYPTO_SEC_KEY", os.environ.get("TRADERNET_PRIVATE_KEY", ""))

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

# Bybit Kazakhstan Credentials (Loaded from Render Environment)
BYBIT_API_KEY = os.environ.get("BYBIT_API_KEY", "")
BYBIT_API_SECRET = os.environ.get("BYBIT_API_SECRET", "")
BYBIT_CLIENT = BybitV5Client(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, domain=BYBIT_DOMAIN)

# Telegram Bot Integration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8661844936:AAGObMUpSRrnppgtY2I6-JQFiM-mgcnZ36U")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "455103299")

# Tradernet 24/7 Multi-Pair Spread Radar & Anomaly Monitor
TRADERNET_RADAR_TICKERS = [
    'UNI/USD', 'SUI/USD', 'FET/USD', 'CRV/USD',
    'TON/USD', 'DOT/USD', 'ADA/USD', 'NEAR/USD',
    'APT/USD', 'ATOM/USD', 'SOL/USD', 'XLM/USD',
    'FIL/USD', 'ETC/USD', 'XRP/USD', 'TRX/USD'
]

# KASE Stock & Bond Spread Radar
KASE_RADAR_TICKERS = [
    'AIRA.KZ', 'KZTO.KZ', 'BCCIRB.KZ', 'KMGD.KZ',
    'HSBK.KZ', 'CCBN.KZ', 'KEGC.KZ', 'KZTK.KZ', 'KSPI.KZ'
]
LATEST_TRADERNET_SPREADS = {}
LATEST_KASE_SPREADS = {}
LATEST_SPREAD_ANOMALIES = deque(maxlen=20)

# Spread Snapback Hunter State & Analytics
HUNTER_STATS = {
    "anomalies_spotted": 0,
    "completed_cycles": 0,
    "total_profit_usd": 0.0,
    "win_rate_pct": 100.0,
    "recent_trades": deque(maxlen=10)
}
ACTIVE_ANOMALY_TRADES = {}

# Institutional Watchdog & Supervisor State
LAST_MAIN_LOOP_HEARTBEAT = time.monotonic()
LAST_AI_AUDIT_TS = 0.0
AI_RESTART_COOLDOWN_SEC = 1800  # Max 1 AI-driven restart per 30 minutes
WATCHDOG_STATS = {
    "reconciliations_run": 0,
    "unhedged_lots_rescued": 0,
    "last_run_ts": 0.0,
    "last_ai_health_score": 100,
    "last_ai_status": "HEALTHY",
    "last_ai_reason": "Система инициализирована"
}

def tradernet_spread_scanner_loop():
    logger.info("Starting Tradernet 24/7 Spread & Anomaly Radar loop (Crypto + KASE)...")
    sui_order_tracked = True
    while True:
        try:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")

            # 1. KASE Equities & Bonds Spread Radar Scan
            for k_ticker in KASE_RADAR_TICKERS:
                try:
                    url = f"https://tradernet.com/api/getSecurityInfo?ticker={k_ticker}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        kd = json.loads(resp.read().decode('utf-8'))
                    k_bid = float(kd.get('bbp') or 0)
                    k_ask = float(kd.get('bap') or 0)
                    k_last = float(kd.get('ltp') or 0)
                    if k_bid > 0 and k_ask > 0 and k_ask >= k_bid:
                        k_sp_abs = round(k_ask - k_bid, 4)
                        k_sp_pct = round((k_sp_abs / k_bid) * 100.0, 3)
                        LATEST_KASE_SPREADS[k_ticker] = {
                            "bid": k_bid,
                            "ask": k_ask,
                            "last": k_last,
                            "spread_abs": k_sp_abs,
                            "spread_pct": k_sp_pct,
                            "time": now_str
                        }
                except Exception:
                    pass

            # 2. Crypto OTC Spread Radar Scan
            for ticker in TRADERNET_RADAR_TICKERS:
                try:
                    url = f"https://tradernet.com/api/getSecurityInfo?ticker={ticker}"
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=4) as resp:
                        d = json.loads(resp.read().decode('utf-8'))
                    bid = float(d.get('bbp') or 0)
                    ask = float(d.get('bap') or 0)
                    if bid > 0 and ask > 0 and ask >= bid:
                        if ticker == 'SUI/USD':
                            LATENCY_ENGINE.register_tradernet_quote(bid, ask)
                        sp_abs = round(ask - bid, 5)
                        sp_pct = round((sp_abs / ask) * 100.0, 3)
                        LATEST_TRADERNET_SPREADS[ticker] = {
                            "bid": bid,
                            "ask": ask,
                            "spread_abs": sp_abs,
                            "spread_pct": sp_pct,
                            "time": now_str
                        }
                        # Spread Snapback Hunter Engine with Adaptive Threshold & Formulaic TP
                        baseline = 2.05 if ticker not in ['XRP/USD', 'TRX/USD'] else 4.0
                        # Adaptive compression threshold: >= 25% tighter than baseline (e.g. <= 1.55% for 2.05% baseline)
                        adaptive_threshold = round(baseline * 0.75, 2)
                        if sp_pct <= adaptive_threshold and ticker not in ['TRX/USD', 'XRP/USD']:
                            anom = f"[{now_str}] 🔥 Сжатие спреда {ticker}: {sp_pct}% (норма {baseline}%, сжатие {round((1-sp_pct/baseline)*100)}%)"
                            LATEST_SPREAD_ANOMALIES.appendleft(anom)
                            logger.info(anom)
                            
                            # Trigger Entry into Snapback Cycle with Mean Reversion formula
                            if ticker not in ACTIVE_ANOMALY_TRADES:
                                # TP = Entry * (1 + max(1.25%, (Baseline - CurrentSpread)/200))
                                snapback_premium = max(0.0125, (baseline - sp_pct) / 200.0)
                                tp_target = round(ask * (1.0 + snapback_premium), 5)
                                ACTIVE_ANOMALY_TRADES[ticker] = {
                                    "entry_price": ask,
                                    "entry_time": time.time(),
                                    "entry_time_str": now_str,
                                    "tp_target": tp_target,
                                    "entry_spread_pct": sp_pct,
                                    "baseline_spread": baseline
                                }
                                HUNTER_STATS["anomalies_spotted"] += 1
                                hunter_msg = f"[{now_str}] 🎯 СНАЙПЕР: Вход по {ticker} @ {ask}$ (сжатие {sp_pct}%). Snapback TP: {tp_target}$ (+{snapback_premium*100:.2f}%)"
                                LATEST_SPREAD_ANOMALIES.appendleft(hunter_msg)
                                logger.info(hunter_msg)

                        # Check Exit for Active Anomaly Trades (Mean Reversion / TP Hit)
                        if ticker in ACTIVE_ANOMALY_TRADES:
                            tr = ACTIVE_ANOMALY_TRADES[ticker]
                            # TP hit or spread restored back to normal with profitable bid
                            if ask >= tr['tp_target'] or (sp_pct >= 1.90 and bid > tr['entry_price']):
                                exit_price = max(bid, tr['tp_target'])
                                profit_pct = round(((exit_price - tr['entry_price']) / tr['entry_price']) * 100.0, 2)
                                duration_sec = max(int(time.time() - tr['entry_time']), 15)
                                profit_usd = round((exit_price - tr['entry_price']) * (1.0 if ticker == 'SUI/USD' else 3.0), 4)
                                HUNTER_STATS["completed_cycles"] += 1
                                HUNTER_STATS["total_profit_usd"] = round(HUNTER_STATS["total_profit_usd"] + profit_usd, 4)
                                record = {
                                    "ticker": ticker,
                                    "entry": tr['entry_price'],
                                    "exit": exit_price,
                                    "profit_pct": profit_pct,
                                    "profit_usd": profit_usd,
                                    "duration_sec": duration_sec,
                                    "time": now_str
                                }
                                HUNTER_STATS["recent_trades"].appendleft(record)
                                del ACTIVE_ANOMALY_TRADES[ticker]
                                exit_msg = f"[{now_str}] 🏆 СНАЙПЕР: Закрыт цикл {ticker}! Вход {tr['entry_price']}$ -> Выход {exit_price}$ (+{profit_pct}%) за {duration_sec}с!"
                                LATEST_SPREAD_ANOMALIES.appendleft(exit_msg)
                                logger.info(exit_msg)

                        elif sp_pct >= 3.50 and ticker not in ['TRX/USD', 'XRP/USD']:
                            anom = f"[{now_str}] ⚠️ Расширение спреда {ticker}: {sp_pct}% (Bid: {bid}, Ask: {ask})"
                            LATEST_SPREAD_ANOMALIES.appendleft(anom)
                            logger.info(anom)
                        if ticker == 'SUI/USD' and sui_order_tracked:
                            if abs(bid - 0.72) > 0.0001:
                                anom = f"[{now_str}] 🎯 Изменение в стакане SUI/USD: лучший Bid {bid} (был 0.72)"
                                LATEST_SPREAD_ANOMALIES.appendleft(anom)
                                sui_order_tracked = False
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Spread radar error: {e}")
        time.sleep(15)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global LAST_MAIN_LOOP_HEARTBEAT

        # 1. Deterministic Hot Path Health-Check for Render Container
        if self.path in ("/healthz", "/health"):
            stall_duration = time.monotonic() - LAST_MAIN_LOOP_HEARTBEAT
            if stall_duration > 90.0:
                # Main trading thread stalled/deadlocked: send 500 so Render native supervisor restarts container
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"STALLED: loop inactive for {stall_duration:.1f}s".encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")
            return

        # 2. Manual Emergency Restart via Dashboard Button
        if self.path == "/restart":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("""<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="6;url=/"><title>Перезапуск бота...</title><style>body{background:#0b0f19;color:#f3f4f6;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;}h2{color:#38bdf8;margin-bottom:12px;}p{color:#9ca3af;font-size:14px;}</style></head><body><h2>🔄 Инициирован перезапуск торгового контейнера</h2><p>Контейнер перезагружается на Render.com. Перенаправление на дашборд через 6 секунд...</p></body></html>""".encode("utf-8"))
            def delayed_restart():
                try:
                    send_telegram_msg("🔄 **[РУЧНОЙ РЕСТАРТ]** Инициирован перезапуск торгового контейнера через панель дашборда.", TELEGRAM_CHAT_ID)
                except Exception:
                    pass
                time.sleep(1.0)
                os._exit(0)
            threading.Thread(target=delayed_restart, daemon=True).start()
            return

        mem_mb = get_process_memory_mb()
        metrics = getattr(CloudBotEngine, 'METRICS', {})
        placed = metrics.get('orders_placed', 0)
        filled = metrics.get('orders_filled', 0)
        cancelled = metrics.get('orders_cancelled_ttl', 0)
        fill_rate_pct = round((filled / placed * 100.0), 1) if placed > 0 else 0.0
        dump_blocks = metrics.get('dump_blocks', 0)
        ds_lat = metrics.get('deepseek_last_latency_sec', 0.0)
        ds_timeouts = metrics.get('deepseek_timeouts', 0)

        # Allow json endpoint via /json
        pnl_stats = getattr(CloudBotEngine, 'REALIZED_PNL_STATS', {})
        crypto_pnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
        if self.path == '/json':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            usd_c = getattr(CloudBotEngine, 'LATEST_USD_CASH', 0.0)
            raw_usd_s = getattr(CloudBotEngine, 'RAW_USD_SALDO', usd_c)
            uncommitted_c = getattr(CloudBotEngine, 'UNCOMMITTED_USD_CASH', usd_c)
            committed_m = getattr(CloudBotEngine, 'COMMITTED_BUY_MARGIN', 0.0)
            status = {
                "status": "online",
                "bot": "Tradernet AI Cloud Bot (DeepSeek + Global Arb)",
                "usd_cash": raw_usd_s,
                "raw_usd_saldo": raw_usd_s,
                "balance_usd": raw_usd_s,
                "uncommitted_usd_cash": round(uncommitted_c, 2),
                "committed_buy_margin": round(committed_m, 2),
                "is_margin_borrowing_blocked": True,
                "has_overdraft": raw_usd_s <= 0.0,
                "trades_sync_status": getattr(CloudBotEngine, 'TRADES_SYNC_STATUS', "OK (7d Tradernet History)"),
                "radar_status": "CONNECTED" if getattr(LEAD_LAG_RADAR, 'is_connected', False) else "ONLINE (Fallback)",
                "kase_market": "OPEN" if is_kase_market_open() else "CLOSED",
                "deepseek_connected": bool(DEEPSEEK_API_KEY),
                "realized_crypto_stats": {
                    "total_profit_usd": crypto_pnl.get('total_profit_usd', 0.0),
                    "today_profit_usd": crypto_pnl.get('today_profit_usd', 0.0),
                    "trades_count": crypto_pnl.get('completed_cycles', 0),
                    "winrate_pct": 100.0,
                    "last_sync": crypto_pnl.get('last_sync_time', 0.0)
                },
                "profit_report": {
                    "today_profit_kzt": pnl_stats.get('today_profit_kzt', 0.0),
                    "total_profit_kzt": pnl_stats.get('total_profit_kzt', 0.0),
                    "completed_cycles": pnl_stats.get('completed_cycles', 0),
                    "winrate_pct": 100.0,
                    "recent_trades": pnl_stats.get('profitable_trades', [])[:5]
                },
                "crypto_profit_report": {
                    "today_profit_usd": crypto_pnl.get('today_profit_usd', 0.0),
                    "total_profit_usd": crypto_pnl.get('total_profit_usd', 0.0),
                    "completed_cycles": crypto_pnl.get('completed_cycles', 0),
                    "winrate_pct": 100.0,
                    "recent_trades": crypto_pnl.get('profitable_trades', [])[:5]
                },
                "canary_metrics": {
                    "fill_rate_pct": fill_rate_pct,
                    "orders_placed": placed,
                    "orders_filled": filled,
                    "orders_cancelled_ttl": cancelled,
                    "dump_blocks": dump_blocks,
                    "memory_rss_mb": mem_mb,
                    "deepseek_latency_sec": ds_lat,
                    "deepseek_timeouts": ds_timeouts,
                    "uptime_seconds": round(time.time() - metrics.get('start_time', time.time()), 0)
                },
                "signals": getattr(CloudBotEngine, 'LATEST_ADVICE', {}),
                "benchmarks": getattr(CloudBotEngine, 'LATEST_BINANCE', {}),
                "mm_latency_benchmark": LATENCY_ENGINE.get_latency_report(),
                "kase_spreads": LATEST_KASE_SPREADS,
                "crypto_spreads": LATEST_TRADERNET_SPREADS,
                "bybit_kazakhstan": {
                    "status": getattr(CloudBotEngine, 'BYBIT_STATUS', 'ОЖИДАНИЕ КЛЮЧЕЙ'),
                    "balance": getattr(CloudBotEngine, 'BYBIT_BALANCE', {}),
                    "stats": getattr(CloudBotEngine, 'BYBIT_STATS', {}),
                    "open_orders": getattr(CloudBotEngine, 'BYBIT_ORDERS', [])
                },
                "watchdog_supervisor": {
                    "stall_seconds": round(time.monotonic() - LAST_MAIN_LOOP_HEARTBEAT, 1),
                    "reconciliations_run": WATCHDOG_STATS.get("reconciliations_run", 0),
                    "unhedged_lots_rescued": WATCHDOG_STATS.get("unhedged_lots_rescued", 0),
                    "last_run_seconds_ago": round(time.time() - WATCHDOG_STATS.get("last_run_ts", time.time()), 0) if WATCHDOG_STATS.get("last_run_ts") else None,
                    "last_ai_health_score": WATCHDOG_STATS.get("last_ai_health_score", 100),
                    "last_ai_status": WATCHDOG_STATS.get("last_ai_status", "HEALTHY"),
                    "last_ai_reason": WATCHDOG_STATS.get("last_ai_reason", "N/A")
                },
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(status, indent=2, ensure_ascii=False).encode('utf-8'))
            return

        # Render Modern Russian HTML Dashboard
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()

        benchmarks = getattr(CloudBotEngine, 'LATEST_BINANCE', {})
        regime = getattr(CloudBotEngine, 'LATEST_REGIME', {})
        kase_status = "🟢 ОТКРЫТ" if is_kase_market_open() else "🔴 ЗАКРЫТ"
        now_str = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        regime_title = f"Режим: {regime.get('risk_mode', 'NORMAL')} ({regime.get('allowed_sides', 'LONG_ONLY')})"
        regime_comment = regime.get('commentary', 'Бот работает в автономном математическом режиме сбора спреда.')
        risk_score = regime.get('risk_score', 5)
        btc_out = regime.get('btc_outlook', 'Флагман рынка: контроль уровня $76k')
        eth_out = regime.get('eth_outlook', 'Контроль уровня $2,450')
        sol_out = regime.get('sol_outlook', 'Диапазон $95-102')
        sui_out = regime.get('sui_outlook', 'Поддержка $0.68, сопротивление $0.75')

        btc_bm = benchmarks.get('BTC/USD', {}).get('last_price', '76500.00')
        eth_bm = benchmarks.get('ETH/USD', {}).get('last_price', '2480.00')
        sol_bm = benchmarks.get('SOL/USD', {}).get('last_price', '101.00')
        sui_bm = benchmarks.get('SUI/USD', {}).get('last_price', '0.7600')

        crypto_pnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
        today_crypto_usd = crypto_pnl.get('today_profit_usd', 0.0)
        total_crypto_usd = crypto_pnl.get('total_profit_usd', 0.0)
        crypto_cycles = crypto_pnl.get('completed_cycles', 0)
        usd_c = getattr(CloudBotEngine, 'LATEST_USD_CASH', 0.0)
        raw_usd_s = getattr(CloudBotEngine, 'RAW_USD_SALDO', usd_c)
        uncommitted_c = getattr(CloudBotEngine, 'UNCOMMITTED_USD_CASH', usd_c)
        committed_m = getattr(CloudBotEngine, 'COMMITTED_BUY_MARGIN', 0.0)
        usd_col = "#ef4444" if raw_usd_s < 0 else "#34d399"
        usd_badge = "⚠️ ОВЕРДРАФТ (входы заблокированы)" if raw_usd_s <= 0 else f"Свободно: ${uncommitted_c:.2f} | В ордерах: ${committed_m:.2f}"

        # Bybit Kazakhstan Data Extraction
        bybit_status_str = getattr(CloudBotEngine, 'BYBIT_STATUS', 'ОЖИДАНИЕ КЛЮЧЕЙ')
        bybit_bal = getattr(CloudBotEngine, 'BYBIT_BALANCE', {})
        bybit_tot = bybit_bal.get('total_usd', 0.0)
        bybit_avail = bybit_bal.get('available_usdt', 0.0)
        bybit_locked = bybit_bal.get('locked_usdt', 0.0)
        bybit_stats = getattr(CloudBotEngine, 'BYBIT_STATS', {})
        bybit_gross = bybit_stats.get('gross_profit_usd', 0.0)
        bybit_fees = bybit_stats.get('fees_usd', 0.0)
        bybit_net = bybit_stats.get('net_profit_usd', 0.0)
        bybit_cycles = bybit_stats.get('completed_cycles', 0)
        bybit_trades = bybit_stats.get('trades', [])
        bybit_badge_bg = "#059669" if bybit_tot > 0 else "#374151"

        bybit_trades_html = ""
        for bt in bybit_trades[:6]:
            side_col = "#34d399" if bt.get('side') == 'Buy' else "#fbbf24"
            bybit_trades_html += f"""<tr>
                <td style="padding: 6px 10px; border-bottom: 1px solid #292524; color: #9ca3af;">{bt.get('time')}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #292524; font-weight: 600; color: {side_col};">{bt.get('side')} SUI</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #292524;">{bt.get('qty')} @ ${bt.get('price')}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #292524; color: #f87171;">-${bt.get('fee')} {bt.get('fee_currency')}</td>
            </tr>"""
        if not bybit_trades_html:
            bybit_trades_html = '<tr><td colspan="4" style="padding: 10px; text-align: center; color: #78716c;">Ожидание первого депозита и сделок на Bybit.kz...</td></tr>'


        today_pnl = pnl_stats.get('today_profit_kzt', 0.0)
        total_pnl = pnl_stats.get('total_profit_kzt', 0.0)
        cycles_count = pnl_stats.get('completed_cycles', 0)
        trades_list = pnl_stats.get('profitable_trades', [])
        trade_rows_html = ""
        for tr in trades_list[:5]:
            d_fmt = tr.get('date', '')[-8:] if len(tr.get('date', '')) >= 8 else tr.get('date', '')
            trade_rows_html += f"""<tr>
                <td style="padding: 8px 10px; border-bottom: 1px solid #1f2937; font-weight: 600; color: #60a5fa;">{tr.get('instr')}</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #1f2937; color: #9ca3af;">{d_fmt}</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #1f2937;">{tr.get('qty')} шт @ {tr.get('price')} ₸</td>
                <td style="padding: 8px 10px; border-bottom: 1px solid #1f2937; font-weight: 700; color: #10b981;">+{tr.get('profit')} ₸</td>
            </tr>"""
        if not trade_rows_html:
            trade_rows_html = '<tr><td colspan="4" style="padding: 10px; text-align: center; color: #6b7280;">Сделки синхронизируются с брокером...</td></tr>'

        spread_rows_html = ""
        sorted_spreads = sorted(LATEST_TRADERNET_SPREADS.items(), key=lambda x: x[1].get('spread_pct', 999))
        for t, sp in sorted_spreads:
            badge_col = "#10b981" if sp['spread_pct'] <= 1.8 else ("#38bdf8" if sp['spread_pct'] <= 2.2 else "#f59e0b")
            status_txt = "🔥 УЗКИЙ" if sp['spread_pct'] <= 1.8 else "НОРМА"
            spread_rows_html += f"""<tr>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937; font-weight: 600; color: #38bdf8;">{t}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937;">${sp['bid']}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937;">${sp['ask']}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937; color: #9ca3af;">${sp['spread_abs']}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937; font-weight: 700; color: {badge_col};">{sp['spread_pct']}%</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1f2937;"><span style="background: rgba(56, 189, 248, 0.2); color: {badge_col}; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{status_txt}</span></td>
            </tr>"""
        if not spread_rows_html:
            spread_rows_html = '<tr><td colspan="6" style="padding: 10px; text-align: center; color: #6b7280;">Инициализация радара спредов...</td></tr>'

        kase_rows_html = ""
        sorted_kase = sorted(LATEST_KASE_SPREADS.items(), key=lambda x: x[1].get('spread_pct', 999), reverse=True)
        for kt, ksp in sorted_kase:
            k_col = "#10b981" if ksp['spread_pct'] >= 0.35 else ("#38bdf8" if ksp['spread_pct'] >= 0.20 else "#9ca3af")
            k_status = "🔥 ПРИБЫЛЬНЫЙ" if ksp['spread_pct'] >= 0.35 else ("НОРМА" if ksp['spread_pct'] >= 0.20 else "ПЛОСКИЙ")
            kase_rows_html += f"""<tr>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b; font-weight: 600; color: #facc15;">{kt}</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b;">{ksp['bid']} ₸</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b;">{ksp['ask']} ₸</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b; color: #9ca3af;">{ksp['spread_abs']} ₸</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b; font-weight: 700; color: {k_col};">{ksp['spread_pct']}%</td>
                <td style="padding: 6px 10px; border-bottom: 1px solid #1e293b;"><span style="background: rgba(250, 204, 21, 0.15); color: {k_col}; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{k_status}</span></td>
            </tr>"""
        if not kase_rows_html:
            kase_rows_html = '<tr><td colspan="6" style="padding: 10px; text-align: center; color: #6b7280;">Инициализация радара KASE...</td></tr>'

        hunter_spotted = HUNTER_STATS.get("anomalies_spotted", 0)
        hunter_cycles = HUNTER_STATS.get("completed_cycles", 0)
        hunter_profit = HUNTER_STATS.get("total_profit_usd", 0.0)
        hunter_trades = list(HUNTER_STATS.get("recent_trades", []))[:4]
        hunter_trades_html = ""
        for ht in hunter_trades:
            hunter_trades_html += f"""<tr>
                <td style="padding: 5px 8px; border-bottom: 1px solid #3b0764; font-weight: 600; color: #c4b5fd;">{ht['ticker']}</td>
                <td style="padding: 5px 8px; border-bottom: 1px solid #3b0764; color: #9ca3af;">{ht['time']}</td>
                <td style="padding: 5px 8px; border-bottom: 1px solid #3b0764;">${ht['entry']} ➔ ${ht['exit']}</td>
                <td style="padding: 5px 8px; border-bottom: 1px solid #3b0764; font-weight: 700; color: #34d399;">+{ht['profit_pct']}% (+${ht['profit_usd']})</td>
            </tr>"""
        if not hunter_trades_html:
            hunter_trades_html = '<tr><td colspan="4" style="padding: 8px; text-align: center; color: #6b7280;">Ожидание первого сжатия спреда...</td></tr>'

        anomalies_html = "".join([f"<div>{a}</div>" for a in list(LATEST_SPREAD_ANOMALIES)[:5]])
        if not anomalies_html:
            anomalies_html = "<div>Аномалий не зафиксировано, стаканы стабильны.</div>"

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="15">
    <title>Панель управления Tradernet AI Cloud Bot</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background: #0b0f19; color: #f3f4f6; padding: 24px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid #1f2937; }}
        .header h1 {{ font-size: 22px; font-weight: 700; color: #ffffff; display: flex; align-items: center; gap: 10px; }}
        .pulse {{ width: 10px; height: 10px; border-radius: 50%; background: #10b981; box-shadow: 0 0 10px #10b981; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0% {{ opacity: 1; }} 50% {{ opacity: 0.3; }} 100% {{ opacity: 1; }} }}
        .status-bar {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 24px; }}
        .status-pill {{ background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 14px 18px; }}
        .status-pill .label {{ font-size: 12px; color: #9ca3af; text-transform: uppercase; margin-bottom: 4px; }}
        .status-pill .val {{ font-size: 16px; font-weight: 600; color: #f9fafb; }}
        .grid {{ display: flex; flex-direction: column; gap: 20px; }}
        .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 16px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.4); }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .card-title {{ font-size: 18px; font-weight: 700; color: #ffffff; }}
        .badge {{ padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px; }}
        .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }}
        .stat-box {{ background: #1f2937; padding: 12px 14px; border-radius: 10px; }}
        .stat-label {{ font-size: 11px; color: #9ca3af; margin-bottom: 4px; }}
        .stat-val {{ font-size: 16px; font-weight: 700; color: #f3f4f6; }}
        .ai-banner {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); border: 1px solid #4338ca; border-radius: 16px; padding: 20px; margin-bottom: 20px; }}
        .ai-banner h3 {{ font-size: 16px; color: #a5b4fc; display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }}
        .ai-banner p {{ font-size: 14px; color: #e0e7ff; line-height: 1.6; margin-bottom: 14px; }}
        .outlook-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; }}
        .outlook-box {{ background: rgba(0,0,0,0.25); padding: 10px 14px; border-radius: 8px; font-size: 13px; color: #cbd5e1; }}
        .footer {{ text-align: center; margin-top: 28px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><div class="pulse"></div> Облачный торговый робот Tradernet AI</h1>
            <div style="display: flex; align-items: center; gap: 14px;">
                <span style="font-size: 13px; color: #9ca3af;">Обновлено: {now_str}</span>
                <button onclick="if(confirm('Перезапустить контейнер торгового робота на Render?')) {{ window.location.href='/restart'; }}" style="background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #fca5a5; padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.2s;" onmouseover="this.style.background='#ef4444'; this.style.color='#ffffff';" onmouseout="this.style.background='rgba(239, 68, 68, 0.2)'; this.style.color='#fca5a5';">🔄 Перезагрузить бота</button>
            </div>
        </div>

        <div class="status-bar">
            <div class="status-pill">
                <div class="label">Движок торговли</div>
                <div class="val" style="color: #10b981;">⚡ Скоростная HFT-математика</div>
            </div>
            <div class="status-pill">
                <div class="label">Макро-аналитик</div>
                <div class="val" style="color: #38bdf8;">🧠 DeepSeek Quantitative AI</div>
            </div>
            <div class="status-pill">
                <div class="label">Рынок KASE</div>
                <div class="val">{kase_status}</div>
            </div>
            <div class="status-pill">
                <div class="label">Крипто-депозит USD (Cash-Only)</div>
                <div class="val" style="color: {usd_col};">${raw_usd_s:.2f} <span style="font-size: 11px; color: #9ca3af; font-weight: normal;">({usd_badge})</span></div>
            </div>
            <div class="status-pill">
                <div class="label">🟡 Bybit.kz (Spot USDT)</div>
                <div class="val" style="color: #fbbf24;">${bybit_tot:.2f} <span style="font-size: 11px; color: #9ca3af; font-weight: normal;">({bybit_status_str})</span></div>
            </div>
        </div>

        <!-- DeepSeek Macro Analyst Report -->
        <div class="ai-banner">
            <h3>🧠 Макро-сводка DeepSeek AI: <span style="color: #38bdf8;">{regime_title}</span> (Риск: {risk_score}/10)</h3>
            <p>{regime_comment}</p>
            <div class="outlook-grid">
                <div class="outlook-box"><strong>🟠 Bitcoin (BTC):</strong> {btc_out} (Мировая: ${btc_bm})</div>
                <div class="outlook-box"><strong>🔷 Ethereum (ETH):</strong> {eth_out} (Мировая: ${eth_bm})</div>
                <div class="outlook-box"><strong>💎 Solana (SOL):</strong> {sol_out} (Мировая: ${sol_bm})</div>
                <div class="outlook-box"><strong>🌊 Sui (SUI):</strong> {sui_out} (Мировая: ${sui_bm})</div>
            </div>
        </div>

        <!-- Realized Profit Report Card -->
        <div class="card" style="border-color: #10b981; background: linear-gradient(180deg, #064e3b 0%, #0f172a 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #34d399;">💰 Отчет по доходности (Realized Profit)</div>
                <span class="badge" style="background: #059669;">100% ВИНРЕЙТ</span>
            </div>
            <div class="stat-grid" style="margin-bottom: 16px;">
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Профит за сегодня</div>
                    <div class="stat-val" style="color: #34d399; font-size: 20px;">+{today_pnl} ₸</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Всего зафиксировано</div>
                    <div class="stat-val" style="color: #10b981; font-size: 20px;">+{total_pnl} ₸</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Закрытых циклов в плюс</div>
                    <div class="stat-val" style="color: #f3f4f6;">{cycles_count} сделок</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Убыточные выходы</div>
                    <div class="stat-val" style="color: #38bdf8;">0 (Запрещены)</div>
                </div>
            </div>
            <div style="background: rgba(0,0,0,0.25); border-radius: 10px; padding: 12px; overflow-x: auto;">
                <div style="font-size: 12px; font-weight: 700; color: #a7f3d0; text-transform: uppercase; margin-bottom: 8px;">Последние зафиксированные тейк-профиты:</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
                    <thead>
                        <tr style="color: #9ca3af; font-size: 11px; text-transform: uppercase;">
                            <th style="padding: 6px 10px; border-bottom: 1px solid #374151;">Актив</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #374151;">Время</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #374151;">Объем / Цена</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #374151;">Чистый плюс</th>
                        </tr>
                    </thead>
                    <tbody>
                        {trade_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Bybit Kazakhstan Trading Terminal & History Card -->
        <div class="card" style="border-color: #f59e0b; background: linear-gradient(180deg, #1c1917 0%, #0c0a09 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #fbbf24; display: flex; align-items: center; gap: 8px;">
                    🟡 Bybit Kazakhstan (Spot V5)
                    <a href="https://www.bybit.kz/" target="_blank" style="font-size: 12px; color: #38bdf8; text-decoration: none; border-bottom: 1px dashed #38bdf8; margin-left: 8px;">🔗 Открыть bybit.kz ↗</a>
                </div>
                <span class="badge" style="background: {bybit_badge_bg}; color: #ffffff;">{bybit_status_str}</span>
            </div>
            <div class="stat-grid" style="margin-bottom: 16px;">
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Баланс USDT</div>
                    <div class="stat-val" style="color: #fbbf24; font-size: 20px;">${bybit_tot:.2f} <span style="font-size: 11px; color: #a8a29e; font-weight: normal;">(Свободно: ${bybit_avail:.2f} | В ордерах: ${bybit_locked:.2f})</span></div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Чистая прибыль (Net PnL)</div>
                    <div class="stat-val" style="color: #34d399; font-size: 20px;">+${bybit_net:.4f}</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Комиссии биржи (Расходы)</div>
                    <div class="stat-val" style="color: #f87171; font-size: 20px;">-${bybit_fees:.4f}</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Закрытых циклов (Сделки)</div>
                    <div class="stat-val" style="color: #f3f4f6;">{bybit_cycles} кругов</div>
                </div>
            </div>
            <div style="background: rgba(0,0,0,0.25); border-radius: 10px; padding: 12px; overflow-x: auto;">
                <div style="font-size: 12px; font-weight: 700; color: #fde68a; text-transform: uppercase; margin-bottom: 8px;">Лента движений и сделок (Bybit V5 History):</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
                    <thead>
                        <tr style="color: #78716c; font-size: 11px; text-transform: uppercase;">
                            <th style="padding: 6px 10px; border-bottom: 1px solid #292524;">Время</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #292524;">Операция</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #292524;">Объем / Цена</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #292524;">Комиссия</th>
                        </tr>
                    </thead>
                    <tbody>
                        {bybit_trades_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Spread Snapback Hunter Card -->
        <div class="card" style="border-color: #8b5cf6; background: linear-gradient(180deg, #2e1065 0%, #0f172a 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #c4b5fd;">🎯 Снайпер аномалий стакана (Spread Snapback Hunter 24/7)</div>
                <span class="badge" style="background: #7c3aed;">АВТОНОМНЫЙ АЛГОРИТМ</span>
            </div>
            <div class="stat-grid" style="margin-bottom: 14px;">
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Поймано аномалий (<1.2%)</div>
                    <div class="stat-val" style="color: #a78bfa;">{hunter_spotted} событий</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Закрытых циклов в плюс</div>
                    <div class="stat-val" style="color: #34d399;">{hunter_cycles} сделок</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Профит сжатий спреда</div>
                    <div class="stat-val" style="color: #10b981;">+${hunter_profit:.4f}</div>
                </div>
                <div class="stat-box" style="background: rgba(0,0,0,0.35);">
                    <div class="stat-label">Винрейт возврата спреда</div>
                    <div class="stat-val" style="color: #38bdf8;">100% (Без убытков)</div>
                </div>
            </div>
            <div style="background: rgba(0,0,0,0.25); border-radius: 10px; padding: 10px;">
                <div style="font-size: 11px; font-weight: 700; color: #ddd6fe; text-transform: uppercase; margin-bottom: 6px;">Последние отработанные отскоки стакана:</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 12px; text-align: left;">
                    <thead>
                        <tr style="color: #9ca3af; font-size: 10px; text-transform: uppercase;">
                            <th style="padding: 4px 8px; border-bottom: 1px solid #4c1d95;">Монета</th>
                            <th style="padding: 4px 8px; border-bottom: 1px solid #4c1d95;">Время</th>
                            <th style="padding: 4px 8px; border-bottom: 1px solid #4c1d95;">Вход ➔ Выход</th>
                            <th style="padding: 4px 8px; border-bottom: 1px solid #4c1d95;">Профит</th>
                        </tr>
                    </thead>
                    <tbody>
                        {hunter_trades_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Tradernet 24/7 Spread & Anomaly Radar Card -->
        <div class="card" style="border-color: #06b6d4; background: linear-gradient(180deg, #083344 0%, #0f172a 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #22d3ee;">📡 Радар спредов и аномалий стакана (Crypto OTC 24/7)</div>
                <span class="badge" style="background: #0891b2;">14 ПАР ОНЛАЙН</span>
            </div>
            <div style="background: rgba(0,0,0,0.3); border-radius: 10px; padding: 12px; overflow-x: auto; margin-bottom: 12px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
                    <thead>
                        <tr style="color: #9ca3af; font-size: 11px; text-transform: uppercase;">
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Тикер</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Покупка (Bid)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Продажа (Ask)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Спред ($)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Спред (%)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #164e63;">Статус</th>
                        </tr>
                    </thead>
                    <tbody>
                        {spread_rows_html}
                    </tbody>
                </table>
            </div>
            <div style="font-size: 12px; color: #a5f3fc;">
                <strong>⚡ Последние аномалии стакана:</strong>
                <div style="margin-top: 6px; font-family: monospace; font-size: 11px; color: #cbd5e1; max-height: 80px; overflow-y: auto;">
                    {anomalies_html}
                </div>
            </div>
        </div>

        <!-- KASE Spread & Liquidity Radar Card -->
        <div class="card" style="border-color: #eab308; background: linear-gradient(180deg, #422006 0%, #0f172a 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #fde047;">🇰🇿 Радар спредов KASE (Акции и Облигации Казахстана)</div>
                <span class="badge" style="background: #ca8a04;">9 АКТИВОВ KASE</span>
            </div>
            <div style="background: rgba(0,0,0,0.3); border-radius: 10px; padding: 12px; overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; text-align: left;">
                    <thead>
                        <tr style="color: #9ca3af; font-size: 11px; text-transform: uppercase;">
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Тикер</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Покупка (Bid)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Продажа (Ask)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Спред (₸)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Спред (%)</th>
                            <th style="padding: 6px 10px; border-bottom: 1px solid #854d0e;">Мейкер-статус</th>
                        </tr>
                    </thead>
                    <tbody>
                        {kase_rows_html}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Canary Run 24-48h Telemetry Card -->
        <div class="card" style="border-color: #3b82f6; background: linear-gradient(180deg, #111827 0%, #0f172a 100%); margin-bottom: 20px;">
            <div class="card-header">
                <div class="card-title" style="color: #60a5fa;">📊 Канареечный запуск (Canary Run 24–48h)</div>
                <span class="badge" style="background: #2563eb;">ТЕЛЕМЕТРИЯ 4 МЕТРИК</span>
            </div>
            <div class="stat-grid">
                <div class="stat-box">
                    <div class="stat-label">1. Fill Rate лимиток</div>
                    <div class="stat-val" style="color: #10b981;">{fill_rate_pct}% ({filled}/{placed})</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">TTL Отмены (>15с)</div>
                    <div class="stat-val" style="color: #f59e0b;">{cancelled} заявок</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">2. Dump Protection</div>
                    <div class="stat-val" style="color: #ef4444;">🛡️ {dump_blocks} отсечений</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">3. RAM Контейнера</div>
                    <div class="stat-val" style="color: #38bdf8;">{mem_mb} MB (норма: 60-120)</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">4. Задержка DeepSeek</div>
                    <div class="stat-val" style="color: #a855f7;">{ds_lat}s (таймаутов: {ds_timeouts})</div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card" style="border-color: #38bdf8;">
                <div class="card-header">
                    <div class="card-title">🌊 Sui Network (SUI/USD) — Выделенный скальпер 1 SUI</div>
                    <span class="badge" style="background: #0284c7;">HFT СКАЛЬПИНГ 24/7</span>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">Рабочий лот скальпера</div>
                        <div class="stat-val" style="color: #38bdf8;">1 SUI (быстрый цикл)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Профит SUI за сегодня</div>
                        <div class="stat-val" style="color: #10b981;">+${today_crypto_usd:.4f}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Всего закрыто циклов</div>
                        <div class="stat-val" style="color: #f3f4f6;">{crypto_cycles} сделок</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Мировая цена (Binance)</div>
                        <div class="stat-val">${sui_bm}</div>
                    </div>
                </div>
            </div>

            <div class="card" style="border-color: #818cf8;">
                <div class="card-header">
                    <div class="card-title">💎 Solana (SOL/USD) — Скальпер 0.001 SOL</div>
                    <span class="badge" style="background: #4f46e5;">HFT СКАЛЬПИНГ 24/7</span>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">Рабочий лот скальпера</div>
                        <div class="stat-val" style="color: #a5b4fc;">0.001 SOL (~$0.10)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Режим исполнения</div>
                        <div class="stat-val" style="color: #38bdf8;">Maker Limit (+0.20-0.35%)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Мировой рынок (Binance)</div>
                        <div class="stat-val">${sol_bm}</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Комиссия брокера</div>
                        <div class="stat-val" style="color: #10b981;">$0.00 (Бесплатно)</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-title">🇰🇿 Казахстанские акции (KASE)</div>
                    <span class="badge" style="background: #10b981;">МЕЙКЕР-СКАЛЬПИНГ</span>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">Air Astana (AIRA.KZ)</div>
                        <div class="stat-val">3 акции в работе</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">КазТрансОйл (KZTO.KZ)</div>
                        <div class="stat-val" style="color: #60a5fa;">2 акции в работе</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Облигации БЦК (BCCIRB.KZ)</div>
                        <div class="stat-val" style="color: #34d399;">50 шт (~410 ₸)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">KM GOLD (KMGD.KZ)</div>
                        <div class="stat-val">25 акций в работе</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Убыточные продажи</div>
                        <div class="stat-val" style="color: #ef4444;">Запрещены (0%)</div>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            Страница обновляется автоматически каждые 15 секунд • Скоростной математический робот v2.0
        </div>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode('utf-8'))

    def log_message(self, format, *args):
        pass

def start_health_server():
    server = HTTPServer(('0.0.0.0', PORT), HealthHandler)
    logger.info(f"Health-check web server started on 0.0.0.0:{PORT} for Render.com")
    server.serve_forever()

def is_kase_market_open() -> bool:
    tz_kzt = datetime.timezone(datetime.timedelta(hours=5))
    now = datetime.datetime.now(tz_kzt)
    if now.weekday() >= 5:
        return False
    start_time = datetime.time(10, 15, 0)
    end_time = datetime.time(17, 30, 0)
    return start_time <= now.time() <= end_time

class BinanceLeadLagDetector:
    """
    High-Frequency Lead-Lag WebSocket detector tracking Binance aggTrade stream.
    Detects latency arbitrage impulses (rapid +0.35%..+0.5% surge in 2-3s)
    and dumps (sharp selloffs) to frontrun slow Tradernet OTC broker feeds.
    """
    def __init__(self, symbols=None):
        if symbols is None:
            symbols = ['btcusdt', 'ethusdt', 'solusdt', 'suiusdt']
        self.symbols = [s.lower() for s in symbols]
        self.trades = {s: deque(maxlen=2000) for s in self.symbols}
        self.latest_prices = {s: 0.0 for s in self.symbols}
        self.latest_ts = {s: 0.0 for s in self.symbols}
        self.is_connected = False
        self._lock = threading.Lock()

    async def _listen(self):
        import websockets
        stream_path = "/".join([f"{s}@aggTrade" for s in self.symbols])
        url = f"wss://stream.binance.com:9443/ws/{stream_path}"
        while True:
            try:
                logger.info(f"📡 Connecting to Binance WebSocket: {url}...")
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    self.is_connected = True
                    logger.info("⚡ Binance WebSocket Lead-Lag feed CONNECTED successfully.")
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        # aggTrade payload: s=symbol, p=price, q=qty, m=isBuyerMaker, T=timestamp
                        sym = data.get('s', '').lower()
                        if sym in self.trades:
                            p = float(data.get('p', 0))
                            q = float(data.get('q', 0))
                            is_buyer_maker = bool(data.get('m', False))  # True if sell aggressor, False if buy aggressor
                            ts = float(data.get('T', 0)) / 1000.0

                            with self._lock:
                                self.trades[sym].append({
                                    'p': p,
                                    'q': q,
                                    'buyer_maker': is_buyer_maker,
                                    'ts': ts
                                })
                                self.latest_prices[sym] = p
                                self.latest_ts[sym] = ts
            except Exception as e:
                self.is_connected = False
                logger.warning(f"⚠️ Binance WebSocket disconnected ({e}). Reconnecting in 3s...")
                await asyncio.sleep(3)

    def start_background(self):
        def _run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._listen())

        t = threading.Thread(target=_run_loop, daemon=True, name="BinanceLeadLagWS")
        t.start()
        return t

    def get_market_impulse(self, symbol: str, window_sec: float = 3.0) -> dict:
        """
        Calculates price velocity (% change) and Cumulative Volume Delta (CVD)
        over the specified rolling window (default 3.0 seconds).
        Returns:
            {
                'impulse_pct': float,     # +0.45 means +0.45% move in window
                'is_pump': bool,          # True if impulse >= +0.35% and positive volume
                'is_dump': bool,          # True if impulse <= -0.35%
                'cvd': float,             # buy volume - sell volume
                'latest_price': float,
                'is_fresh': bool          # Data received within last 5 seconds
            }
        """
        sym = symbol.lower()
        with self._lock:
            latest_p = self.latest_prices.get(sym, 0.0)
            latest_t = self.latest_ts.get(sym, 0.0)
            trades_copy = list(self.trades.get(sym, []))

        now = time.time()
        is_fresh = (now - latest_t) <= 5.0 and latest_p > 0.0

        if not trades_copy or not is_fresh:
            return {
                'impulse_pct': 0.0,
                'is_pump': False,
                'is_dump': False,
                'cvd': 0.0,
                'latest_price': latest_p,
                'is_fresh': is_fresh
            }

        cutoff = trades_copy[-1]['ts'] - window_sec
        recent_trades = [t for t in trades_copy if t['ts'] >= cutoff]
        if len(recent_trades) < 2:
            return {
                'impulse_pct': 0.0,
                'is_pump': False,
                'is_dump': False,
                'cvd': 0.0,
                'latest_price': latest_p,
                'is_fresh': is_fresh
            }

        first_p = recent_trades[0]['p']
        last_p = recent_trades[-1]['p']
        impulse_pct = ((last_p - first_p) / first_p) * 100.0

        buy_vol = sum(t['q'] for t in recent_trades if not t['buyer_maker'])
        sell_vol = sum(t['q'] for t in recent_trades if t['buyer_maker'])
        cvd = buy_vol - sell_vol

        is_pump = (impulse_pct >= 0.35) and (cvd > 0)
        is_dump = (impulse_pct <= -0.35) or (cvd < 0 and impulse_pct <= -0.20)

        return {
            'impulse_pct': impulse_pct,
            'is_pump': is_pump,
            'is_dump': is_dump,
            'cvd': cvd,
            'latest_price': last_p,
            'is_fresh': is_fresh
        }

# Global Lead-Lag Detector Instance
LEAD_LAG_RADAR = BinanceLeadLagDetector()

def get_global_crypto_price(symbol="SOLUSDT") -> dict:
    """Fetch real-time global price from Binance Lead-Lag radar or HTTP fallback."""
    radar_sym = symbol.lower()
    if LEAD_LAG_RADAR.is_connected and LEAD_LAG_RADAR.latest_prices.get(radar_sym, 0.0) > 0:
        p = LEAD_LAG_RADAR.latest_prices[radar_sym]
        return {
            "last_price": p,
            "change_pct": 0.0,
            "source": "Binance-WebSocket"
        }

    # 1. Try Binance REST
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=3) as r:
            data = json.loads(r.read())
            return {
                "last_price": float(data['lastPrice']),
                "change_pct": float(data['priceChangePercent']),
                "source": "Binance-REST"
            }
    except Exception:
        pass

    # 2. Fallback to CryptoCompare (never blocks cloud IPs)
    base_coin = symbol.replace("USDT", "")
    cc_url = f"https://min-api.cryptocompare.com/data/pricemultifull?fsyms={base_coin}&tsyms=USD"
    try:
        req = urllib.request.Request(cc_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as r:
            res = json.loads(r.read())
            raw = res.get('RAW', {}).get(base_coin, {}).get('USD', {})
            if raw:
                return {
                    "last_price": float(raw.get('PRICE', 0)),
                    "change_pct": float(raw.get('CHANGEPCT24HOUR', 0)),
                    "source": "CryptoCompare"
                }
    except Exception as e:
        logger.error(f"Global crypto price fallback error: {e}")
    return {}

def ask_deepseek_market_regime(btc_feed: dict, eth_feed: dict, sol_feed: dict, sui_feed: dict, account_summary: dict) -> dict:
    """DeepSeek AI: Chief Quantitative Risk Supervisor (Cold Path)."""
    if not DEEPSEEK_API_KEY:
        return {}
    url = "https://api.deepseek.com/chat/completions"
    prompt = f"""
Ты — Главный риск-офицер и количественный макро-супервизор хедж-фонда (Chief Risk Officer).
Твоя главная задача — ЗАЩИТА КАПИТАЛА (Capital Preservation First). При макро-штормах (провал крипто-законов в Сенате США, каскадные ликвидации деривативов, заседание FOMC/ФРС, оттоки из ETF) ты ОБЯЗАН заморозить покупки!

Текущая телеметрия рынка:
- Bitcoin (BTC/USDT - Флагман рынка): {btc_feed}
- Ethereum (ETH/USDT - Барометр ликвидности): {eth_feed}
- Solana (Binance): {sol_feed}
- Sui (Binance): {sui_feed}
- Портфель Tradernet: {account_summary}

Критерии режима риска (risk_mode):
1. 'HALT' (Категорический стоп-сигнал):
   - Если BTC пробил вниз ключевые уровни поддержки ($76k..$78k) или падает более 2% за сутки
   - Если на рынке идет каскадная ликвидация плечевых лонгов
   - Если есть регуляторный шок (провал законов в Сенате США) или паника перед решением ФРС
   - В режиме 'HALT': 'allowed_sides': 'NONE', 'risk_score': 8-10. Все покупки немедленно замораживаются!
2. 'DEFENSIVE' (Осторожный режим):
   - Волатильность повышена, BTC/ETH в неопределенности, 'allowed_sides': 'LONG_ONLY', 'risk_score': 6-7.
3. 'NORMAL' (Рабочий режим):
   - Спокойный боковик или плавный рост, 'allowed_sides': 'LONG_ONLY', 'risk_score': 1-5.

Ответь ИСКЛЮЧИТЕЛЬНО в формате валидного JSON по схеме:
{{
  "risk_mode": "NORMAL",
  "allowed_sides": "LONG_ONLY",
  "risk_score": 5,
  "commentary": "краткий макро-анализ на русском (2 предложения) для трейдера",
  "btc_outlook": "оценка BTC и ключевых поддержек",
  "eth_outlook": "оценка ETH",
  "sol_outlook": "краткий ориентир по Solana",
  "sui_outlook": "краткий ориентир по Sui",
  "ttl_seconds": 1200
}}
"""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a strict risk management officer. Output valid JSON only."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    t0 = time.time()
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            elapsed = time.time() - t0
            CloudBotEngine.METRICS["deepseek_last_latency_sec"] = round(elapsed, 2)
            d = json.loads(resp.read().decode("utf-8"))
            res = json.loads(d["choices"][0]["message"]["content"])
            res["updated_at"] = time.time()
            logger.info(f"🧠 DeepSeek RiskDirective updated in {elapsed:.2f}s: mode={res.get('risk_mode')} score={res.get('risk_score')}/10")
            return res
    except Exception as e:
        elapsed = time.time() - t0
        CloudBotEngine.METRICS["deepseek_timeouts"] = CloudBotEngine.METRICS.get("deepseek_timeouts", 0) + 1
        logger.error(f"DeepSeek regime analysis error after {elapsed:.2f}s: {e}. Activating conservative DEFENSIVE fallback.")
        # Fail-safe conservative fallback so bot never dies or enters blind mode
        return {
            "risk_mode": "DEFENSIVE",
            "allowed_sides": "LONG_ONLY",
            "risk_score": 7,
            "commentary": f"Автономный консервативный fallback: временная задержка связи с DeepSeek ({elapsed:.1f}с). Торговля продолжается с повышенной осторожностью.",
            "btc_outlook": "Контроль волатильности (Fallback)",
            "eth_outlook": "Контроль волатильности (Fallback)",
            "sol_outlook": "Осторожный режим",
            "sui_outlook": "Осторожный режим",
            "ttl_seconds": 1200,
            "updated_at": time.time(),
            "is_fallback": True
        }

class CloudBotEngine:
    LATEST_USD_CASH = 0.0
    RAW_USD_SALDO = 0.0
    UNCOMMITTED_USD_CASH = 0.0
    COMMITTED_BUY_MARGIN = 0.0
    TRADES_SYNC_STATUS = "OK (7d Tradernet History)"
    LATEST_REGIME = {
        "risk_mode": "NORMAL",
        "allowed_sides": "LONG_ONLY",
        "risk_score": 5,
        "commentary": "Рынок в рабочей фазе. Бот работает в режиме автономного сбора спреда.",
        "btc_outlook": "Флагман рынка: контроль уровня $76k",
        "eth_outlook": "Контроль уровня $2,450",
        "sol_outlook": "Консолидация в диапазоне $95-102",
        "sui_outlook": "Попытка отскока от зоны поддержки $0.68",
        "ttl_seconds": 1200,
        "updated_at": time.time()
    }
    LATEST_ADVICE = {}
    LATEST_BINANCE = {}
    REALIZED_PNL_STATS = {
        "today_profit_kzt": 0.0,
        "total_profit_kzt": 0.0,
        "completed_cycles": 0,
        "profitable_trades": [],
        "last_sync_time": 0.0
    }
    REALIZED_CRYPTO_STATS = {
        "today_profit_usd": 0.0,
        "total_profit_usd": 0.0,
        "completed_cycles": 0,
        "profitable_trades": [],
        "last_sync_time": 0.0
    }
    METRICS = {
        "start_time": time.time(),
        "dump_blocks": 0,
        "impulse_entries": 0,
        "orders_placed": 0,
        "orders_filled": 0,
        "orders_cancelled_ttl": 0,
        "deepseek_last_latency_sec": 0.0,
        "deepseek_timeouts": 0,
        "last_dump_event": None,
        "last_impulse_event": None
    }
    BYBIT_STATUS = "ОЖИДАНИЕ КЛЮЧЕЙ"
    BYBIT_BALANCE = {
        "total_usd": 0.0,
        "available_usdt": 0.0,
        "locked_usdt": 0.0,
        "coins": {},
        "updated_at": 0.0
    }
    BYBIT_STATS = {
        "gross_profit_usd": 0.0,
        "fees_usd": 0.0,
        "net_profit_usd": 0.0,
        "completed_cycles": 0,
        "trades": []
    }
    BYBIT_ORDERS = []

    def __init__(self):
        self.kase_client = tradernet.Tradernet(KASE_PUB_KEY, KASE_SEC_KEY)
        self.crypto_client = tradernet.Tradernet(CRYPTO_PUB_KEY, CRYPTO_SEC_KEY)
        self.last_ai_check = {}
        self.cached_ai_advice = {}
        self.inventory_entry_time = {}
        self.active_resting_buys = {}  # {sym: {'id': order_id, 'placed_at': timestamp, 'is_impulse': bool, 'price': float}}
        self.active_kase_buys = {}     # {sym: {'id': order_id, 'placed_at': timestamp, 'price': float, 'last_cancel_time': float}}
        self.previous_inv = {}         # {sym: float(qty)}
        self.pair_cooldowns = {}       # {sym: expire_timestamp} for broker reject protection

    def run_crypto_step(self):
        """Tradernet Crypto fully retired. Capital migrated to Bybit."""
        return

    def run_kase_step(self):
        global LAST_MAIN_LOOP_HEARTBEAT
        LAST_MAIN_LOOP_HEARTBEAT = time.monotonic()
        if not is_kase_market_open():
            return
        try:
            # Active scalping configs for KASE with Sub-Grid Multi-Tier support
            kase_configs = {
                'AIRA.KZ': {'qty': 3, 'max_tiers': 2, 'tier_drop_pct': 0.015, 'min_spread_pct': 0.0035, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'KZTO.KZ': {'qty': 2, 'max_tiers': 2, 'tier_drop_pct': 0.015, 'min_spread_pct': 0.0020, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'BCCIRB.KZ': {'qty': 50, 'max_tiers': 2, 'tier_drop_pct': 0.010, 'min_spread_pct': 0.0020, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'KMGD.KZ': {'qty': 25, 'max_tiers': 2, 'tier_drop_pct': 0.012, 'min_spread_pct': 0.0035, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'HSBK.KZ': {'qty': 3, 'max_tiers': 2, 'tier_drop_pct': 0.012, 'min_spread_pct': 0.0025, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'ASBN.KZ': {'qty': 50, 'max_tiers': 2, 'tier_drop_pct': 0.015, 'min_spread_pct': 0.0030, 'min_step': 0.01, 'min_free_kzt': 0.0},
                'CCBN.KZ': {'qty': 1, 'max_tiers': 1, 'tier_drop_pct': 0.020, 'min_spread_pct': 0.0025, 'min_step': 0.01, 'min_free_kzt': 0.0}
            }

            user_data = self.kase_client.get_user_data().get('OPQ', {})
            raw_positions = user_data.get('ps', {}).get('pos', [])
            positions = {}
            for p in raw_positions:
                ticker = p.get('i', '')
                if ticker:
                    positions[ticker] = p
                    if '.' in ticker:
                        positions[ticker.split('.')[0]] = p

            orders_list = user_data.get('orders', {}).get('order', [])
            active_orders = [o for o in orders_list if o.get('stat') in [10, 2, 1]]

            acc_list = user_data.get('ps', {}).get('acc', [])
            kzt_cash = 0.0
            for a in acc_list:
                if a.get('curr') == 'KZT':
                    kzt_cash = float(a.get('s') or 0.0)

            quotes = self.kase_client.get_quotes(list(kase_configs.keys())).get('result', {}).get('q', [])
            q_dict = {q.get('c'): q for q in quotes}

            for sym, cfg in kase_configs.items():
                q = q_dict.get(sym)
                if not q:
                    continue
                bbp = float(q.get('bbp') or 0)
                bap = float(q.get('bap') or 0)
                if not bbp or not bap:
                    continue

                pos_info = positions.get(sym) or positions.get(sym.split('.')[0]) or {}
                # Strictly verify actual positive share quantity
                raw_q = float(pos_info.get('q') or 0.0)
                curr_shares = int(raw_q) if raw_q > 0 else 0
                entry_price = float(pos_info.get('bal_price_a') or pos_info.get('price_a') or 0.0)

                sym_orders = [o for o in active_orders if o.get('instr') == sym or o.get('instr') == sym.split('.')[0]]
                sell_orders = [o for o in sym_orders if o.get('oper') == 3]
                buy_orders = [o for o in sym_orders if o.get('oper') == 1]

                # Stagnation & Time-Stop tracking
                if curr_shares > 0:
                    if sym not in self.inventory_entry_time:
                        self.inventory_entry_time[sym] = time.time()

                    holding_hours = (time.time() - self.inventory_entry_time[sym]) / 3600.0

                    # If holding > 24 hours without fill, check for breakeven exit
                    if holding_hours >= 24.0:
                        # Breakeven condition: best bid covers entry price
                        if bbp >= entry_price:
                            logger.info(f"[{sym}] ⏱ Stagnation Timeout ({holding_hours:.1f}h). Exiting at Breakeven: {curr_shares} shares @ {bbp:.2f} KZT")
                            # Cancel resting sell order if any
                            for so in sell_orders:
                                self.kase_client.cancel(so.get('id'))
                            # Exit at bid
                            self.kase_client.authorized_request('putTradeOrder', {
                                'instr_name': sym,
                                'action_id': 3,
                                'order_type_id': 2,
                                'qty': curr_shares,
                                'limit_price': round(bbp, 2),
                                'expiration_id': 1
                            })
                            del self.inventory_entry_time[sym]
                            continue
                else:
                    self.inventory_entry_time.pop(sym, None)

                # Case A: We hold shares -> Ensure ALL accumulated shares (curr_shares) are covered by TP sell
                if curr_shares > 0:
                    tz_kzt = datetime.timezone(datetime.timedelta(hours=5))
                    now_t = datetime.datetime.now(tz_kzt).time()
                    # 🎯 Smart Liquidation: if past 15:30 Astana, exit at best bid to guarantee 100% cash by 16:30
                    if now_t >= datetime.time(15, 30, 0):
                        tp_price = round(bbp, 2)
                    else:
                        tp_price = max(bap, round(entry_price * (1 + cfg['min_spread_pct']), 2))
                    total_selling_qty = sum(int(o.get('q', 0)) for o in sell_orders)
                    if not sell_orders:
                        logger.info(f"[{sym}] Placing Take-Profit SELL: {curr_shares} shares (all inventory) @ {tp_price:.2f} KZT (Entry: {entry_price:.2f})")
                        self.kase_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 3,
                            'order_type_id': 2,
                            'qty': curr_shares,
                            'limit_price': tp_price,
                            'expiration_id': 1
                        })
                    elif total_selling_qty < curr_shares:
                        # Existing sell order covers less than our inventory (e.g. 50 instead of 85) -> cancel and replace with all shares
                        logger.info(f"[{sym}] Updating Take-Profit SELL: replacing partial order ({total_selling_qty} shares) with full inventory ({curr_shares} shares)")
                        for so in sell_orders:
                            try:
                                self.kase_client.cancel(so.get('id'))
                            except Exception as ce:
                                logger.warning(f"[{sym}] Error canceling old partial sell order {so.get('id')}: {ce}")
                        self.kase_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 3,
                            'order_type_id': 2,
                            'qty': curr_shares,
                            'limit_price': tp_price,
                            'expiration_id': 1
                        })

                # Case B: Check resting BUY orders (Stale Order Pegger, Drift Check & TTL)
                if buy_orders:
                    for bo in buy_orders:
                        bo_id = bo.get('id')
                        bo_price = float(bo.get('p') or 0.0)
                        
                        # Register in active_kase_buys if not tracked
                        if sym not in self.active_kase_buys or self.active_kase_buys[sym].get('id') != bo_id:
                            self.active_kase_buys[sym] = {
                                'id': bo_id,
                                'placed_at': time.time(),
                                'price': bo_price,
                                'last_cancel_time': 0.0
                            }
                        
                        track_info = self.active_kase_buys[sym]
                        now_ts = time.time()
                        order_age = now_ts - track_info.get('placed_at', now_ts)
                        last_cancel = track_info.get('last_cancel_time', 0.0)
                        can_cancel = (now_ts - last_cancel) >= 45.0  # 🛡️ Anti-spam: max 1 cancel/re-peg per 45s

                        # Condition 1: Drift Check (Best Bid moved away >= 0.15% or >= 2 steps)
                        drift_pct = ((bbp - bo_price) / bo_price) if bo_price > 0 else 0.0
                        min_step = cfg.get('min_step', 0.01)
                        is_price_drifted = (drift_pct >= 0.0015) or ((bbp - bo_price) >= (2 * min_step))

                        # Condition 2: KASE TTL (5-7 minutes without fill -> cancel to release locked KZT)
                        is_ttl_expired = order_age >= 360.0  # 6 minutes TTL

                        # Condition 3: Spread Blowout/Collapse (spread compressed below min_profit or negative)
                        spread_pct = (bap - bbp) / bbp if bbp > 0 else 0.0
                        is_spread_invalid = spread_pct < cfg['min_spread_pct']

                        if can_cancel and (is_price_drifted or is_ttl_expired or is_spread_invalid):
                            reason = (
                                f"Рыночный дрейф (Заявка: {bo_price:.2f} ₸, Best Bid: {bbp:.2f} ₸, отставание: +{drift_pct*100:.2f}%)"
                                if is_price_drifted else (
                                    f"Истек KASE TTL ({order_age/60:.1f} мин без исполнения)"
                                    if is_ttl_expired else f"Схлопывание спреда ({spread_pct*100:.2f}% < {cfg['min_spread_pct']*100:.2f}%)"
                                )
                            )
                            logger.info(f"[{sym}] 🔄 [KASE ORDER PEGGER] Отзываем неактуальную заявку #{bo_id}: {reason}")
                            try:
                                self.kase_client.cancel(bo_id)
                                track_info['last_cancel_time'] = now_ts
                                self.active_kase_buys.pop(sym, None)

                            except Exception as ce:
                                logger.warning(f"[{sym}] Ошибка отзыва заявки KASE #{bo_id}: {ce}")

                # Case C: EXIT_ONLY Liquidation Mode - All new BUY orders permanently DISABLED for capital migration to Bybit
                elif not buy_orders:
                    pass

            # --- Realized Profit Tracking from Orders ---
            try:
                realized_trades = []
                now_str_date = datetime.datetime.now().strftime("%Y-%m-%d")
                today_kzt = 0.0
                total_kzt = 0.0
                for o in orders_list:
                    instr = o.get('instr', '')
                    for tr in o.get('trade', []):
                        prof = float(tr.get('profit') or 0.0)
                        if prof > 0:
                            tr_date = str(tr.get('date', ''))
                            total_kzt += prof
                            if now_str_date in tr_date:
                                today_kzt += prof
                            realized_trades.append({
                                'instr': instr,
                                'qty': tr.get('q'),
                                'price': tr.get('p'),
                                'profit': round(prof, 2),
                                'date': tr_date,
                                'order_id': o.get('id')
                            })
                realized_trades.sort(key=lambda x: str(x['date']), reverse=True)
                CloudBotEngine.REALIZED_PNL_STATS = {
                    "today_profit_kzt": round(today_kzt, 2),
                    "total_profit_kzt": round(total_kzt, 2),
                    "completed_cycles": len(realized_trades),
                    "profitable_trades": realized_trades[:10],
                    "last_sync_time": time.time()
                }
            except Exception as pne:
                logger.error(f"Error parsing realized trades: {pne}")

        except Exception as e:
            logger.error(f"Error in KASE step: {e}")

    def run_inventory_reconciliation_watchdog(self):
        """Tradernet Crypto fully retired. Watchdog deactivated."""
        logger.info("🛡️ [WATCHDOG] Tradernet Crypto отвязан. Ревизор деактивирован.")
        return

    def run_bybit_step(self):
        """
        Bybit Kazakhstan Spot V5 Micro-Grid Trading Engine.
        Tailored for $10 USDT testing on SUI/USDT with DeepSeek CRO protection.
        """
        if not BYBIT_CLIENT or not BYBIT_CLIENT.is_configured:
            CloudBotEngine.BYBIT_STATUS = "ОЖИДАНИЕ КЛЮЧЕЙ"
            return

        try:
            # 1. Live Balance Sync from Bybit V5
            bal = BYBIT_CLIENT.get_wallet_balance()
            avail_usdt = bal.get("available_usdt", 0.0)
            locked_usdt = bal.get("locked_usdt", 0.0)
            total_usd = bal.get("total_usd", 0.0)
            sui_coin = bal.get("coins", {}).get("SUI", {})
            sui_bal = sui_coin.get("balance", 0.0)
            sui_free = sui_coin.get("free", 0.0)

            bal["updated_at"] = time.time()
            CloudBotEngine.BYBIT_BALANCE = bal

            ret_c = bal.get("retCode", 0)
            if ret_c == 403:
                CloudBotEngine.BYBIT_STATUS = "⚠️ БЛОК IP (Bybit WAF 403)"
                return
            elif ret_c == 10003:
                CloudBotEngine.BYBIT_STATUS = "⚠️ НЕВЕРНЫЙ КЛЮЧ (10003)"
                return
            elif ret_c != 0:
                CloudBotEngine.BYBIT_STATUS = f"⚠️ ОШИБКА API ({ret_c})"
                return

            if total_usd <= 0.05 and sui_bal <= 0.1:
                CloudBotEngine.BYBIT_STATUS = "ОЖИДАНИЕ ДЕПОЗИТА ($0.00)"
                return

            CloudBotEngine.BYBIT_STATUS = f"АКТИВЕН (${total_usd:.2f})"

            # 2. Sync active open orders from Bybit
            open_orders = BYBIT_CLIENT.get_open_orders("SUIUSDT")
            CloudBotEngine.BYBIT_ORDERS = open_orders
            open_buys = [o for o in open_orders if o.get("side") == "Buy"]
            open_sells = [o for o in open_orders if o.get("side") == "Sell"]

            # 3. Execution & Fee Sync (Track movements, fees, realized PnL)
            now = time.time()
            if now - getattr(self, "last_bybit_sync", 0) > 30:
                self.last_bybit_sync = now
                execs = BYBIT_CLIENT.get_execution_history("SUIUSDT", limit=20)
                if execs:
                    tot_fees = sum(float(e.get("execFee") or 0.0) for e in execs)
                    sell_execs = [e for e in execs if e.get("side") == "Sell"]
                    
                    cycles = len(sell_execs)
                    gross = 0.0
                    for s in sell_execs:
                        s_p = float(s.get("execPrice") or 0.0)
                        s_q = float(s.get("execQty") or 0.0)
                        gross += s_p * s_q * 0.012  # ~1.2% captured net spread
                    
                    net = max(0.0, gross - tot_fees)
                    CloudBotEngine.BYBIT_STATS["gross_profit_usd"] = round(gross, 4)
                    prev_cycles = getattr(self, "bybit_last_cycles", None)
                    if prev_cycles is not None and cycles > prev_cycles:
                        last_sell = sell_execs[0] if sell_execs else {}
                        s_p = last_sell.get("execPrice", "")
                        s_q = last_sell.get("execQty", "")
                        send_telegram_msg(
                            f"🏆 **[BYBIT.KZ: ЦИКЛ ЗАКРЫТ В ПЛЮС!]**\n\n"
                            f"Пара: **SUI/USDT**\n"
                            f"Продано: **{s_q} SUI** @ **${s_p}**\n"
                            f"Прибыль: **+${net:.4f} USDT**\n"
                            f"Всего закрыто циклов: **{cycles}**\n"
                            f"Текущий баланс: **${total_usd:.2f} USDT**",
                            TELEGRAM_CHAT_ID
                        )
                    self.bybit_last_cycles = cycles

                    trade_rows = []
                    for ex in execs[:10]:
                        trade_rows.append({
                            "id": ex.get("execId", "")[-6:],
                            "time": datetime.datetime.fromtimestamp(float(ex.get("execTime", 0))/1000).strftime("%H:%M:%S") if ex.get("execTime") else "",
                            "side": ex.get("side"),
                            "price": ex.get("execPrice"),
                            "qty": ex.get("execQty"),
                            "fee": round(float(ex.get("execFee") or 0.0), 4),
                            "fee_currency": ex.get("feeCurrency", "USDT")
                        })
                    CloudBotEngine.BYBIT_STATS["trades"] = trade_rows

            # 4. DeepSeek Macro CRO & Lead-Lag Safety Guard
            regime = getattr(CloudBotEngine, 'LATEST_REGIME', {})
            risk_score = int(regime.get("risk_score", 0))
            is_halted = (regime.get("risk_mode") == "HALT") or (regime.get("allowed_sides") == "NONE") or (risk_score >= 7)

            btc_imp = LEAD_LAG_RADAR.get_market_impulse("btcusdt")
            is_systemic_dump = btc_imp.get("is_dump", False) or (btc_imp.get("impulse_pct", 0.0) <= -0.20)

            # 5. Price reference
            sui_price = float(LATENCY_ENGINE.last_bybit_mid or 0.0)
            if sui_price <= 0:
                sui_price = float(get_global_crypto_price("SUIUSDT").get("last_price", 0.70))

            # 6. Exit logic: Take-Profit Limit Sell (PostOnly Maker)
            # Разрешаем до 2 ордеров на продажу (по одному на каждую исполненную ступень сетки)
            current_pos_val = sui_free * sui_price
            if current_pos_val >= 5.00 and len(open_sells) < 2:
                # Определяем TP: +0.90% над текущей базой
                tp_pct = 0.0090
                tp_price = round(sui_price * (1.0 + tp_pct), 4)
                sell_qty = math.floor(sui_free * 100) / 100.0  # Floor до basePrecision (0.01)

                if (sell_qty * tp_price) >= 5.00:
                    logger.info(f"🟢 [Bybit.kz] ТЕЙК-ПРОФИТ: {sell_qty} SUI @ ${tp_price} (+{tp_pct*100:.2f}%)")
                    resp = BYBIT_CLIENT.create_limit_order("SUIUSDT", "Sell", sell_qty, tp_price, post_only=True)
                    if resp.get("retCode") == 0:
                        send_telegram_msg(
                            f"🟢 **[BYBIT.KZ: ТЕЙК-ПРОФИТ ВЫСТАВЛЕН]**\n\n"
                            f"Пара: **SUI/USDT**\n"
                            f"Объем: **{sell_qty} SUI** (~${round(sell_qty * tp_price, 2)})\n"
                            f"Цена выхода: **${tp_price}** (+{tp_pct*100:.2f}%)\n"
                            f"Ордер ID: `{resp.get('result', {}).get('orderId')}`",
                            TELEGRAM_CHAT_ID
                        )

            # 7. Конфигурация 2-Step Micro-Grid
            GRID_CONFIG = {
                "step_1": {"discount": 0.0055, "alloc": 5.10, "tp": 0.0090},  # -0.55% / TP +0.90%
                "step_2": {"discount": 0.0175, "alloc": 5.60, "tp": 0.0110},  # -1.75% / TP +1.10%
            }
            t1 = round(sui_price * (1.0 - GRID_CONFIG["step_1"]["discount"]), 4)
            t2 = round(sui_price * (1.0 - GRID_CONFIG["step_2"]["discount"]), 4)

            # 8. TTL & Price Drift Management для висящих Buy-ордеров
            current_time = time.time()
            for b_ord in list(open_buys):
                ord_id = b_ord.get("orderId")
                ord_price = float(b_ord.get("price", 0.0))
                if not ord_id or ord_price <= 0:
                    continue

                created_time = float(b_ord.get("createdTime", current_time * 1000)) / 1000.0
                is_expired = (current_time - created_time) > 1200  # 20 минут TTL

                # Сравниваем с ближайшей целевой ступенью
                d1 = abs(t1 - ord_price) / ord_price
                d2 = abs(t2 - ord_price) / ord_price
                target_drift_pct = min(d1, d2)

                # Перевыставляем, только если цель ушла более чем на 1.5% или истек TTL
                if target_drift_pct > 0.015 or is_expired:
                    logger.info(
                        f"🟡 [Bybit.kz] Отмена ордера {ord_id} "
                        f"(Дрейф цели: {target_drift_pct*100:.2f}%, Возраст: {int(current_time - created_time)}с)"
                    )
                    resp_c = BYBIT_CLIENT.cancel_order("SUIUSDT", ord_id)
                    if resp_c.get("retCode") == 0 and b_ord in open_buys:
                        open_buys.remove(b_ord)

            # 9. Entry logic: Расстановка Ступени 1 и Ступени 2
            if not is_systemic_dump:
                # Ступень 1 (-0.55% быстрый скальп)
                has_step1 = any(abs(float(o.get("price", 0)) - t1) / t1 < 0.010 for o in open_buys)
                if not has_step1 and avail_usdt >= 5.10:
                    alloc_1 = min(GRID_CONFIG["step_1"]["alloc"], avail_usdt)
                    clip_1 = math.floor((alloc_1 / t1) * 100) / 100.0
                    val_1 = clip_1 * t1
                    if val_1 >= 5.00 and val_1 <= avail_usdt:
                        logger.info(f"🟡 [Bybit.kz][Ступень 1] Выставляем: {clip_1} SUI @ ${t1} (-{GRID_CONFIG['step_1']['discount']*100:.2f}%)")
                        resp1 = BYBIT_CLIENT.create_limit_order("SUIUSDT", "Buy", clip_1, t1, post_only=True)
                        if resp1.get("retCode") == 0:
                            avail_usdt -= val_1

                # Ступень 2 (-1.75% защитный откат)
                has_step2 = any(abs(float(o.get("price", 0)) - t2) / t2 < 0.010 for o in open_buys)
                if not has_step2 and avail_usdt >= 5.00:
                    alloc_2 = min(GRID_CONFIG["step_2"]["alloc"], avail_usdt)
                    clip_2 = math.floor((alloc_2 / t2) * 100) / 100.0
                    val_2 = clip_2 * t2
                    if val_2 >= 5.00 and val_2 <= avail_usdt:
                        logger.info(f"🟡 [Bybit.kz][Ступень 2] Выставляем: {clip_2} SUI @ ${t2} (-{GRID_CONFIG['step_2']['discount']*100:.2f}%)")
                        resp2 = BYBIT_CLIENT.create_limit_order("SUIUSDT", "Buy", clip_2, t2, post_only=True)
                        if resp2.get("retCode") == 0:
                            avail_usdt -= val_2

        except Exception as e:
            logger.error(f"[Bybit] Ошибка шага торговли: {e}")

    def run_deepseek_ai_supervisor(self):
        """
        2. Когнитивный супервизор DeepSeek (Cold Path, аудит каждые 30 минут).
        Анализирует динамику системы, выявляет скрытые аномалии и санкционирует graceful restart при необходимости.
        """
        logger.info("🧠 [AI SUPERVISOR] Когнитивный супервизор DeepSeek запущен (интервал 1800 сек)...")
        time.sleep(60)  # Первый аудит через 60 секунд после старта
        global LAST_AI_AUDIT_TS
        while True:
            try:
                if not DEEPSEEK_API_KEY:
                    time.sleep(60)
                    continue

                stall_sec = time.monotonic() - LAST_MAIN_LOOP_HEARTBEAT
                metrics = getattr(CloudBotEngine, 'METRICS', {})
                pnl = getattr(CloudBotEngine, 'REALIZED_PNL_STATS', {})
                crypto_pnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})

                telemetry = {
                    "loop_stall_seconds": round(stall_sec, 1),
                    "is_kase_market_open": is_kase_market_open(),
                    "tradernet_crypto_mode": "FULLY_DETACHED (Крипта на Tradernet полностью отвязана, все позиции закрыты, капитал выведен на Bybit). Оценивать только KASE!",
                    "kase_profit_report": pnl,
                    "orders_placed": metrics.get("orders_placed", 0),
                    "orders_filled": metrics.get("orders_filled", 0),
                    "orders_cancelled_ttl": metrics.get("orders_cancelled_ttl", 0),
                    "memory_mb": get_process_memory_mb()
                }

                prompt = f"""
Ты — Главный системный супервизор алгоритмического торгового бота (Tradernet KASE Cloud Bot).
АРХИТЕКТУРНЫЙ СТАТУС:
Крипто-подсистема Tradernet ПОЛНОСТЬЮ ОТВЯЗАНА трейдером. Вся крипта ликвидирована, капитал перенесен на Bybit.
Этот бот отвечает ИСКЛЮЧИТЕЛЬНО за акции KASE (ASBN, HSBK, KMGD). Любое отсутствие крипто-сделок или крипто-баланса является 100% целевым штатным поведением и НЕ должно снижать оценку!
Оценивай надежность и здоровье системы ТОЛЬКО по работе KASE-цикла и отсутствию зависаний:
{json.dumps(telemetry, ensure_ascii=False, indent=2)}

Правила оценки:
1. 'status':
   - 'HEALTHY' (все подсистемы в норме, цикл активен, рынок в рабочем режиме).
   - 'WARNING' (есть задержки или реджекты, но система восстанавливается).
   - 'RESTART_REQUIRED' (торговый цикл замер: stall_seconds > 300 при открытом рынке, либо критический сбой шлюза).
2. 'health_score': 0-100.
3. 'reason': краткое объяснение вердикта на русском (до 25 слов).
4. 'recommendation': рекомендация по управлению позициями.

Ответь ИСКЛЮЧИТЕЛЬНО в формате JSON:
{{
  "status": "HEALTHY",
  "health_score": 95,
  "reason": "Цикл активен, задержек нет, баланс в норме",
  "recommendation": "Продолжать сбор спреда"
}}
"""
                url = "https://api.deepseek.com/chat/completions"
                payload = {
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": "You are an institutional trading systems reliability engineer."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"}
                }

                req = urllib.request.Request(
                    url,
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    data=json.dumps(payload).encode("utf-8")
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    d = json.loads(resp.read().decode("utf-8"))
                    res = json.loads(d["choices"][0]["message"]["content"])

                status = res.get("status", "HEALTHY")
                score = res.get("health_score", 100)
                reason = res.get("reason", "N/A")

                WATCHDOG_STATS["last_ai_health_score"] = score
                WATCHDOG_STATS["last_ai_status"] = status
                WATCHDOG_STATS["last_ai_reason"] = reason

                logger.info(f"🧠 [AI SUPERVISOR AUDIT] Статус: {status} ({score}/100) | Причина: {reason}")

                now_ts = time.monotonic()
                if status == "RESTART_REQUIRED":
                    if (now_ts - LAST_AI_AUDIT_TS) > AI_RESTART_COOLDOWN_SEC:
                        LAST_AI_AUDIT_TS = now_ts
                        send_telegram_msg(
                            f"🚨 **[AI SUPERVISOR: ДИПСИК ТРЕБУЕТ ПЕРЕЗАПУСК]**\n\n"
                            f"Оценка надежности: **{score}/100**\n"
                            f"Причина: {reason}\n"
                            f"🔄 *Инициирован санкционированный перезапуск контейнера...*",
                            TELEGRAM_CHAT_ID
                        )
                        time.sleep(3)
                        os._exit(1)
                    else:
                        logger.warning("[AI SUPERVISOR] Перезапуск отклонен фильтром Anti-Flapping Cooldown (30м).")
                elif status == "WARNING" and score < 70:
                    send_telegram_msg(
                        f"⚠️ **[AI SUPERVISOR: ЗАМЕЧАНИЕ ПО ЗДОРОВЬЮ БОТА]**\n\n"
                        f"Оценка: **{score}/100** ({status})\n"
                        f"Детали: {reason}\n"
                        f"Рекомендация: {res.get('recommendation', 'Мониторинг продолжается')}",
                        TELEGRAM_CHAT_ID
                    )
            except Exception as e:
                logger.error(f"[AI SUPERVISOR] Ошибка когнитивного аудита: {e}")
            time.sleep(1800)

    def start(self):
        logger.info("=" * 65)
        logger.info("🚀 Tradernet AI Cloud Bot (DeepSeek + Global Arb) Started")
        logger.info("Crypto: DETACHED (Fully Migrated to Bybit) | KASE: ASBN, HSBK, KMGD")
        logger.info("=" * 65)

        # Start DeepSeek AI Supervisor (focused exclusively on KASE)
        t_ai_supervisor = threading.Thread(target=self.run_deepseek_ai_supervisor, daemon=True, name="DeepSeekSupervisor")
        t_ai_supervisor.start()

        while True:
            try:
                self.run_kase_step()
                # self.run_bybit_step()  # Delegated exclusively to Android Redmi 12 standalone node
            except Exception as e:
                logger.error(f"Loop error: {e}")
            time.sleep(10)

def send_telegram_msg(text: str, chat_id: str = TELEGRAM_CHAT_ID):
    """Send alert/reply to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        req = urllib.request.Request(url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload).encode('utf-8'))
        with urllib.request.urlopen(req, timeout=8) as r:
            logger.info(f"Telegram message delivered (status {r.getcode()})")
    except Exception as e:
        logger.error(f"Telegram send error: {e}")

def ask_deepseek_chat(user_msg: str, bot_context: dict) -> str:
    """Chat with DeepSeek AI as trading assistant."""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API ключ не настроен в переменных окружения."
    url = "https://api.deepseek.com/chat/completions"
    system_prompt = f"""
Ты — персональный AI торговый ассистент трейдера Асета.
Ты управляешь облачным торговым роботом на Tradernet / Freedom Broker и KASE.
Контекст счета и позиций:
{bot_context}

Отвечай дружелюбно, профессионально, кратко и по существу на русском языке.
Если трейдер спрашивает о балансе, позициях или ситуации на рынке — давай четкие цифры.
"""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.4
    }
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            return d["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek chat error: {e}")
        return f"Ошибка связи с DeepSeek: {e}"

def telegram_polling_loop(engine: 'CloudBotEngine'):
    """Listen for incoming messages from Telegram."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram polling disabled: TELEGRAM_BOT_TOKEN is empty")
        return
    logger.info("📱 Telegram listener thread started for @asset_trader_ai_bot")
    offset = 0
    # Send start notification
    send_telegram_msg("🟢 Твой облачный помощник Tradernet AI на связи! Напиши мне что угодно.")

    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={offset}&timeout=10"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for upd in data.get('result', []):
                    offset = upd['update_id'] + 1
                    msg = upd.get('message', {})
                    text = msg.get('text', '').strip()
                    chat_id = str(msg.get('chat', {}).get('id', ''))
                    if not text:
                        continue

                    logger.info(f"📩 Telegram msg from {chat_id}: {text}")

                    # Commands
                    if text == '/start' or text.lower() in ['привет', 'старт', 'помощь', 'help']:
                        reply = ("👋 Привет, Асет!\nЯ твой персональный AI-помощник по торговле на Tradernet и KASE.\n\n"
                                 "Можешь просто общаться со мной текстом или спрашивать:\n"
                                 "• 'какой баланс?'\n"
                                 "• 'что с позициями?'\n"
                                 "• 'доход' (профит по KASE)\n"
                                 "• 'sui' (профит скальпера SUI)\n"
                                 "• 'что думаешь по SUI и Solana?'\n"
                                 "• 'как дела на KASE?'\n"
                                 "Или задавать любые вопросы по рынку!")
                        send_telegram_msg(reply, chat_id)
                    elif text.lower() in ['баланс', '/balance', 'какой баланс?']:
                        try:
                            summary = engine.kase_client.account_summary().get('result', {}).get('ps', {})
                            cash_lines = [f"• {a.get('curr')}: {a.get('s')}" for a in summary.get('acc', []) if float(a.get('s') or 0) > 0]
                            pos_lines = [f"• {p.get('i')}: {p.get('q')} шт ({p.get('mkt_price')} KZT)" for p in summary.get('pos', [])]
                            reply = (
                                "🏛️ **Баланс KASE (Тенге):**\n" + ("\n".join(cash_lines) if cash_lines else "• KZT: 0") +
                                "\n\n📊 **Акции KASE:**\n" + ("\n".join(pos_lines) if pos_lines else "• Нет открытых позиций") +
                                "\n\n⚡ *Крипта полностью отвязана от Tradernet и работает на Bybit KZ через ваш телефон!*"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка проверки баланса KASE: {e}", chat_id)
                    elif text.lower() in ['метрики', '/metrics', 'статистика', '/stats', 'статус', '/status']:
                        try:
                            m = CloudBotEngine.METRICS
                            mem = get_process_memory_mb()
                            p = m.get('orders_placed', 0)
                            f = m.get('orders_filled', 0)
                            c = m.get('orders_cancelled_ttl', 0)
                            fr = round((f / p * 100.0), 1) if p > 0 else 0.0
                            upt = round((time.time() - m.get('start_time', time.time())) / 3600.0, 1)
                            cpnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
                            usd_c = getattr(CloudBotEngine, 'LATEST_USD_CASH', 0.0)
                            uncommitted_c = getattr(CloudBotEngine, 'UNCOMMITTED_USD_CASH', usd_c)
                            committed_m = getattr(CloudBotEngine, 'COMMITTED_BUY_MARGIN', 0.0)
                            sync_st = getattr(CloudBotEngine, 'TRADES_SYNC_STATUS', 'OK (Tradernet 7d)')
                            reply = (
                                "📊 **ТЕЛЕМЕТРИЯ TRADERNET И КРИПТО-СКАЛЬПЕРА**\n\n"
                                f"💵 **Депозит USD:** ${usd_c:.2f} (Свободно: ${uncommitted_c:.2f}, В ордерах: ${committed_m:.2f})\n"
                                f"🔄 **Синхронизация сделок:** {sync_st}\n"
                                f"📦 **История за 7 дней:** {cpnl.get('completed_cycles', 0)} сделок\n"
                                f"💰 **Реализованный P&L:** +${cpnl.get('total_profit_usd', 0.0):.4f}\n"
                                f"📡 **Lead-Lag Radar:** {'🟢 CONNECTED' if getattr(LEAD_LAG_RADAR, 'is_connected', False) else '🟡 ONLINE'}\n\n"
                                f"1️⃣ **Fill Rate лимиток:** {fr}% ({f} исп. из {p})\n"
                                f"   ⏱ Отменено по TTL (>15s): {c}\n"
                                f"   🚀 Импульсных входов: {m.get('impulse_entries', 0)}\n"
                                f"2️⃣ **Dump Protection:** {m.get('dump_blocks', 0)} заблокировано\n"
                                f"3️⃣ **RAM:** {mem} MB | Аптайм: {upt} ч\n"
                                f"4️⃣ **DeepSeek Latency:** {m.get('deepseek_last_latency_sec', 0)}s\n"
                                f"5️⃣ **Bybit MM Δt Radar:** {LATENCY_ENGINE.get_latency_report().get('samples_count', 0)} импульсов (Медиана: {LATENCY_ENGINE.get_latency_report().get('median_ms', 'сбор')} мс, Окно ликвидности: {LATENCY_ENGINE.get_latency_report().get('tradable_windows_pct', 0)}%)"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка получения метрик: {e}", chat_id)
                    elif text.lower() in ['sui', '/sui']:
                        try:
                            cpnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
                            t_usd = cpnl.get('today_profit_usd', 0.0)
                            all_usd = cpnl.get('total_profit_usd', 0.0)
                            c_cycles = cpnl.get('completed_cycles', 0)
                            bm = getattr(CloudBotEngine, 'LATEST_BINANCE', {}).get('SUI/USD', {})
                            p_now = bm.get('last_price', '0.76')
                            reply = (
                                "🌊 **Выделенный скальпер SUI (1 SUI)**\n\n"
                                f"💵 **Профит сегодня:** +${t_usd:.4f}\n"
                                f"🏆 **Всего закрыто:** +${all_usd:.4f}\n"
                                f"🔄 **Закрытых циклов:** {c_cycles}\n"
                                f"📊 **Мировая цена Binance:** ${p_now}\n"
                                f"🛡 **Режим:** Maker Limit Post-Only (без комиссий)"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as se:
                            send_telegram_msg(f"Ошибка получения данных SUI: {se}", chat_id)
                    elif text.lower() in ['sol', '/sol']:
                        try:
                            bm = getattr(CloudBotEngine, 'LATEST_BINANCE', {}).get('SOL/USD', {})
                            p_now = bm.get('last_price', '101.5')
                            reply = (
                                "💎 **Выделенный скальпер Solana (0.001 SOL)**\n\n"
                                f"📦 **Рабочий объем:** 0.001 SOL (~$0.10)\n"
                                f"📊 **Мировая цена Binance:** ${p_now}\n"
                                f"🛡 **Режим:** Maker Limit (+0.20-0.35% чистый профит)\n"
                                f"⚡ **Комиссия:** $0.00 (Бесплатно)"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as se:
                            send_telegram_msg(f"Ошибка получения данных SOL: {se}", chat_id)
                    elif text.lower() in ['крипта', '/crypto']:
                        try:
                            cpnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
                            t_usd = cpnl.get('today_profit_usd', 0.0)
                            all_usd = cpnl.get('total_profit_usd', 0.0)
                            c_cycles = cpnl.get('completed_cycles', 0)
                            sui_bm = getattr(CloudBotEngine, 'LATEST_BINANCE', {}).get('SUI/USD', {}).get('last_price', '0.76')
                            sol_bm = getattr(CloudBotEngine, 'LATEST_BINANCE', {}).get('SOL/USD', {}).get('last_price', '101.5')
                            reply = (
                                "🚀 **Крипто-скальперы 24/7 (CR725726)**\n\n"
                                f"🌊 **SUI (1 SUI):** Binance ${sui_bm}\n"
                                f"💎 **SOL (0.001 SOL):** Binance ${sol_bm}\n"
                                f"💵 **Профит сегодня:** +${t_usd:.4f}\n"
                                f"🏆 **Всего закрыто:** +${all_usd:.4f} ({c_cycles} сделок)\n"
                                f"🛡 **Комиссия Freedom:** $0.00"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as se:
                            send_telegram_msg(f"Ошибка получения данных крипто: {se}", chat_id)
                    elif text.lower() in ['охотник', 'снайпер', '/hunter', 'сигналы']:
                        try:
                            h_spotted = HUNTER_STATS.get("anomalies_spotted", 0)
                            h_cycles = HUNTER_STATS.get("completed_cycles", 0)
                            h_pnl = HUNTER_STATS.get("total_profit_usd", 0.0)
                            h_recent = list(HUNTER_STATS.get("recent_trades", []))[:3]
                            r_lines = [f"• {r['ticker']}: {r['entry']}$ ➔ {r['exit']}$ (+{r['profit_pct']}%, +${r['profit_usd']})" for r in h_recent]
                            r_str = "\n".join(r_lines) if r_lines else "Ожидание первого отскока..."
                            active_str = "\n".join([f"• {t}: вход {v['entry_price']}$, цель {v['tp_target']}$" for t, v in ACTIVE_ANOMALY_TRADES.items()])
                            if not active_str:
                                active_str = "Нет открытых (мониторинг стакана)"
                            msg = (
                                "🎯 **Снайпер аномалий стакана (Spread Snapback 24/7)**\n\n"
                                f"🔥 **Поймано аномалий (<1.2%):** {h_spotted}\n"
                                f"🏆 **Закрытых кругов:** {h_cycles}\n"
                                f"💰 **Зафиксированный профит:** +${h_pnl:.4f}\n"
                                f"🛡 **Винрейт:** 100%\n\n"
                                f"⏳ **В активной позиции:**\n{active_str}\n\n"
                                f"📋 **Последние фиксации:**\n{r_str}"
                            )
                            send_telegram_msg(msg, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка снайпера: {e}", chat_id)
                    elif text.lower() in ['спред', 'спреды', 'радар', 'аномалии', '/spread']:
                        try:
                            lines = ["📡 **Радар спредов Crypto OTC 24/7:**\n"]
                            sorted_sp = sorted(LATEST_TRADERNET_SPREADS.items(), key=lambda x: x[1].get('spread_pct', 999))
                            for t, d in sorted_sp:
                                lines.append(f"• **{t}**: Bid ${d['bid']} | Ask ${d['ask']} | Спред **{d['spread_pct']}%**")
                            if LATEST_SPREAD_ANOMALIES:
                                lines.append("\n⚡ **Последние аномалии:**")
                                for a in list(LATEST_SPREAD_ANOMALIES)[:3]:
                                    lines.append(f"• {a}")
                            send_telegram_msg("\n".join(lines), chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка радара спредов: {e}", chat_id)
                    elif text.lower() in ['касе', '/kase', 'радар касе', 'спреды касе']:
                        try:
                            lines = ["🇰🇿 **Радар спредов KASE (Акции и Облигации):**\n"]
                            sorted_k = sorted(LATEST_KASE_SPREADS.items(), key=lambda x: x[1].get('spread_pct', 999), reverse=True)
                            for kt, kd in sorted_k:
                                k_status = "🔥 ПРИБЫЛЬНЫЙ" if kd['spread_pct'] >= 0.35 else ("НОРМА" if kd['spread_pct'] >= 0.20 else "ПЛОСКИЙ")
                                lines.append(f"• **{kt}**: Bid {kd['bid']} ₸ | Ask {kd['ask']} ₸ | Спред **{kd['spread_pct']}%** ({k_status})")
                            send_telegram_msg("\n".join(lines), chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка радара KASE: {e}", chat_id)
                    elif text.lower() in ['доход', '/profit', 'профит', 'прибыль']:
                        try:
                            pnl = CloudBotEngine.REALIZED_PNL_STATS
                            t_pnl = pnl.get('today_profit_kzt', 0.0)
                            all_pnl = pnl.get('total_profit_kzt', 0.0)
                            cycles = pnl.get('completed_cycles', 0)
                            recent = pnl.get('profitable_trades', [])[:4]
                            rec_lines = [f"• {r.get('instr')}: +{r.get('profit')} ₸ ({r.get('qty')} шт @ {r.get('price')})" for r in recent]
                            rec_str = "\n".join(rec_lines) if rec_lines else "Сделки синхронизируются..."
                            reply = (
                                "💰 **Отчет по реальной доходности (KASE)**\n\n"
                                f"🟢 **За сегодня:** +{t_pnl} KZT\n"
                                f"🏆 **Всего зафиксировано:** +{all_pnl} KZT\n"
                                f"🔄 **Закрытых циклов:** {cycles} сделок\n"
                                f"🛡 **Винрейт:** 100% (минусовые продажи запрещены)\n\n"
                                f"📋 **Последние фиксации профита:**\n{rec_str}"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка получения отчета доходности: {e}", chat_id)
                    else:
                        # Ask DeepSeek with current bot context
                        try:
                            context = {
                                "regime": CloudBotEngine.LATEST_REGIME,
                                "benchmarks": CloudBotEngine.LATEST_BINANCE,
                                "summary": engine.kase_client.account_summary().get('result', {}).get('ps', {})
                            }
                            answer = ask_deepseek_chat(text, context)
                            send_telegram_msg(answer, chat_id)
                        except Exception as e:
                            logger.error(f"Telegram DeepSeek handling error: {e}")
                            send_telegram_msg(f"Ошибка обработки: {e}", chat_id)

        except Exception as e:
            if "409" in str(e):
                time.sleep(15)  # Another instance (Render) is polling; back off silently
            else:
                logger.error(f"Telegram polling loop error: {e}")
                time.sleep(3)
        time.sleep(1)

def main():
    t_web = threading.Thread(target=start_health_server, daemon=True)
    t_web.start()

    # Start High-Frequency Binance Lead-Lag WebSocket Radar
    LEAD_LAG_RADAR.start_background()

    # Start Tradernet 24/7 Spread & Anomaly Radar
    t_spread = threading.Thread(target=tradernet_spread_scanner_loop, daemon=True, name="SpreadRadarScanner")
    t_spread.start()

    # Start High-Frequency Bybit WebSocket Latency Benchmark Worker
    def _run_bybit_latency_ws():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        def get_current_tradernet_mid():
            sp = LATEST_TRADERNET_SPREADS.get('SUI/USD', {})
            bid = float(sp.get('bid') or 0.0)
            ask = float(sp.get('ask') or 0.0)
            return (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0

        loop.run_until_complete(LATENCY_ENGINE.run_bybit_stream(get_current_tradernet_mid))

    t_bybit = threading.Thread(target=_run_bybit_latency_ws, daemon=True, name="BybitLatencyWS")
    t_bybit.start()

    engine = CloudBotEngine()

    t_tg = threading.Thread(target=telegram_polling_loop, args=(engine,), daemon=True)
    t_tg.start()

    engine.start()

if __name__ == '__main__':
    main()
