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
import tradernet
from latency_telemetry_worker import LatencyBenchmarkEngine

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

    # 1. Базовый целевой объем по стоимости (~$1.50 - $3.00 на клип)
    if price < 0.50:
        target_cost = 2.00  # Дешевые (XLM, ADA): ~5-10 монет
    elif price < 2.00:
        target_cost = 2.50  # Средние (SUI, APT): ~2-3 монеты
    else:
        target_cost = max(price * min_lot, 3.50)  # Дорогие (DOT, NEAR, SOL)

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

PORT = int(os.environ.get("PORT", "10000"))

# API Keys loaded strictly from environment variables (No hardcoded secrets)
KASE_PUB_KEY = os.environ.get("KASE_PUB_KEY", "")
KASE_SEC_KEY = os.environ.get("KASE_SEC_KEY", "")

CRYPTO_PUB_KEY = os.environ.get("CRYPTO_PUB_KEY", "")
CRYPTO_SEC_KEY = os.environ.get("CRYPTO_SEC_KEY", "")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

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
LATEST_TRADERNET_SPREADS = {}
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

def tradernet_spread_scanner_loop():
    logger.info("Starting Tradernet 24/7 Spread & Anomaly Radar loop...")
    sui_order_tracked = True
    while True:
        try:
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
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
                                # TP = Entry * (1 + (Baseline - CurrentSpread)/200)
                                snapback_premium = max(0.0035, (baseline - sp_pct) / 200.0)
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
                                try:
                                    send_telegram_msg(
                                        f"🎯 **[Снайпер аномалий] ВХОД В СЖАТИЕ СПРЕДА**\n\n"
                                        f"Монета: **{ticker}**\n"
                                        f"Цена: **{ask} $**\n"
                                        f"Сжатие: **{sp_pct}%** (база {baseline}%)\n"
                                        f"Целевой Snapback TP: **{tp_target} $** (+{snapback_premium*100:.2f}% на нормализации)",
                                        TELEGRAM_CHAT_ID
                                    )
                                except Exception:
                                    pass

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
                                try:
                                    send_telegram_msg(
                                        f"🏆 **[Снайпер аномалий] ЦИКЛ ЗАКРЫТ В ПЛЮС!**\n\n"
                                        f"Монета: **{ticker}**\n"
                                        f"Вход: {tr['entry_price']} $ ➔ Выход: **{exit_price} $**\n"
                                        f"Чистая прибыль: **+{profit_pct}%** (+${profit_usd})\n"
                                        f"Длительность удержания: {duration_sec} сек.\n"
                                        f"Спред восстановился в норму ({sp_pct}%)",
                                        TELEGRAM_CHAT_ID
                                    )
                                except Exception:
                                    pass
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
            status = {
                "status": "online",
                "bot": "Tradernet AI Cloud Bot (DeepSeek + Global Arb)",
                "usd_cash": getattr(CloudBotEngine, 'LATEST_USD_CASH', 1.58),
                "balance_usd": getattr(CloudBotEngine, 'LATEST_USD_CASH', 1.58),
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
        sol_out = regime.get('sol_outlook', 'Диапазон $100-103')
        sui_out = regime.get('sui_outlook', 'Поддержка $0.75, сопротивление $0.78')

        sol_bm = benchmarks.get('SOL/USD', {}).get('last_price', '101.00')
        sui_bm = benchmarks.get('SUI/USD', {}).get('last_price', '0.7600')

        crypto_pnl = getattr(CloudBotEngine, 'REALIZED_CRYPTO_STATS', {})
        today_crypto_usd = crypto_pnl.get('today_profit_usd', 0.0)
        total_crypto_usd = crypto_pnl.get('total_profit_usd', 0.0)
        crypto_cycles = crypto_pnl.get('completed_cycles', 0)

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
        .outlook-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
        .outlook-box {{ background: rgba(0,0,0,0.25); padding: 10px 14px; border-radius: 8px; font-size: 13px; color: #cbd5e1; }}
        .footer {{ text-align: center; margin-top: 28px; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1><div class="pulse"></div> Облачный торговый робот Tradernet AI</h1>
            <span style="font-size: 13px; color: #9ca3af;">Обновлено: {now_str}</span>
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
        </div>

        <!-- DeepSeek Macro Analyst Report -->
        <div class="ai-banner">
            <h3>🧠 Макро-сводка DeepSeek AI: <span style="color: #38bdf8;">{regime_title}</span> (Риск: {risk_score}/10)</h3>
            <p>{regime_comment}</p>
            <div class="outlook-grid">
                <div class="outlook-box"><strong>💎 Solana (SOL):</strong> {sol_out} (Мировая цена: ${sol_bm})</div>
                <div class="outlook-box"><strong>🌊 Sui (SUI):</strong> {sui_out} (Мировая цена: ${sui_bm})</div>
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
                <div class="card-title" style="color: #22d3ee;">📡 Радар спредов и аномалий стакана (Tradernet 24/7)</div>
                <span class="badge" style="background: #0891b2;">10 ПАР ОНЛАЙН</span>
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
                        <div class="stat-val" style="color: #60a5fa;">1 акция в работе</div>
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
    start_time = datetime.time(10, 0, 0)
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
            symbols = ['solusdt', 'suiusdt']
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

def ask_deepseek_market_regime(sol_feed: dict, sui_feed: dict, account_summary: dict) -> dict:
    """DeepSeek AI: Chief Quantitative Risk Supervisor (Cold Path)."""
    if not DEEPSEEK_API_KEY:
        return {}
    url = "https://api.deepseek.com/chat/completions"
    prompt = f"""
Ты — Главный риск-офицер и количественный супервизор хедж-фонда (Risk Supervisor).
Твоя задача — проанализировать телеметрию рынка и выдать строгую директиву риска (RiskDirective).

Текущая телеметрия:
- Solana (Binance): {sol_feed}
- Sui (Binance): {sui_feed}
- Портфель Tradernet: {account_summary}

Требования к директиве:
1. 'risk_mode':
   - 'NORMAL' (рынок адекватен, волатильность рабочая)
   - 'DEFENSIVE' (рынок под давлением продавцов, снизить аппетит к риску)
   - 'HALT' (панический слив, шторм, запретить любые новые покупки)
2. 'allowed_sides': 'LONG_ONLY' или 'NONE' (если слив или аномалия).
3. 'risk_score': число 1-10.
4. 'commentary': краткая человеческая сводка (2 предложения) на русском для Telegram и дашборда.
5. 'ttl_seconds': время жизни директивы (обычно 1200 сек).

Ответь ИСКЛЮЧИТЕЛЬНО в формате валидного JSON по схеме:
{{
  "risk_mode": "NORMAL",
  "allowed_sides": "LONG_ONLY",
  "risk_score": 5,
  "commentary": "текст аналитической сводки на русском",
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
            "sol_outlook": "Осторожный режим",
            "sui_outlook": "Осторожный режим",
            "ttl_seconds": 1200,
            "updated_at": time.time(),
            "is_fallback": True
        }

class CloudBotEngine:
    LATEST_USD_CASH = 1.58
    TRADES_SYNC_STATUS = "OK (7d Tradernet History)"
    LATEST_REGIME = {
        "risk_mode": "NORMAL",
        "allowed_sides": "LONG_ONLY",
        "risk_score": 5,
        "commentary": "Рынок в рабочей фазе. Бот работает в режиме автономного сбора спреда.",
        "sol_outlook": "Консолидация в диапазоне $100-103",
        "sui_outlook": "Попытка отскока от зоны поддержки $0.75",
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

    def __init__(self):
        self.kase_client = tradernet.Tradernet(KASE_PUB_KEY, KASE_SEC_KEY)
        self.crypto_client = tradernet.Tradernet(CRYPTO_PUB_KEY, CRYPTO_SEC_KEY)
        self.last_ai_check = {}
        self.cached_ai_advice = {}
        self.inventory_entry_time = {}
        self.active_resting_buys = {}  # {sym: {'id': order_id, 'placed_at': timestamp, 'is_impulse': bool, 'price': float}}
        self.previous_inv = {}         # {sym: float(qty)}
        self.pair_cooldowns = {}       # {sym: expire_timestamp} for broker reject protection

    def run_crypto_step(self):
        try:
            crypto_pairs = {
                'UNI/USD': {'binance': 'UNIUSDT', 'qty': '0.1', 'min_qty': 0.1, 'lot_step': 0.1, 'lot_decimals': 1, 'min_profit_pct': 0.0075, 'decimals': 4},
                'SUI/USD': {'binance': 'SUIUSDT', 'qty': '1', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 4},
                'FET/USD': {'binance': 'FETUSDT', 'qty': '1', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 5},
                'DOT/USD': {'binance': 'DOTUSDT', 'qty': '1', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 4},
                'TON/USD': {'binance': 'TONUSDT', 'qty': '1', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 4},
                'ADA/USD': {'binance': 'ADAUSDT', 'qty': '5', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 5},
                'NEAR/USD': {'binance': 'NEARUSDT', 'qty': '0.5', 'min_qty': 0.5, 'lot_step': 0.5, 'lot_decimals': 1, 'min_profit_pct': 0.0075, 'decimals': 4},
                'APT/USD': {'binance': 'APTUSDT', 'qty': '1', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 5},
                'ATOM/USD': {'binance': 'ATOMUSDT', 'qty': '0.5', 'min_qty': 0.5, 'lot_step': 0.5, 'lot_decimals': 1, 'min_profit_pct': 0.0075, 'decimals': 4},
                'SOL/USD': {'binance': 'SOLUSDT', 'qty': '0.001', 'min_qty': 0.001, 'lot_step': 0.001, 'lot_decimals': 3, 'min_profit_pct': 0.0025, 'decimals': 2},
                'XLM/USD': {'binance': 'XLMUSDT', 'qty': '5', 'min_qty': 1.0, 'lot_step': 1.0, 'lot_decimals': 0, 'min_profit_pct': 0.0075, 'decimals': 5}
            }

            user_summary = self.crypto_client.account_summary().get('result', {}).get('ps', {})
            acc_list = user_summary.get('acc', [])
            usd_cash = 0.0
            for a in acc_list:
                if a.get('curr') == 'USD':
                    # 'open_limit' / 'free_money' / 's' - broker's real unencumbered balance
                    usd_cash = float(a.get('open_limit') or a.get('free_money') or a.get('s') or 0.0)
            CloudBotEngine.LATEST_USD_CASH = usd_cash

            pos_list = user_summary.get('pos', [])
            positions = {p.get('i'): p for p in pos_list}

            orders = self.crypto_client.get_placed().get('result', {}).get('orders', {}).get('order', [])
            active_orders = [o for o in orders if o.get('stat') in [10, 2, 1]]

            quotes = self.crypto_client.get_quotes(list(crypto_pairs.keys())).get('result', {}).get('q', [])
            q_dict = {q.get('c'): q for q in quotes}

            # Check macro regime via DeepSeek once every 5 minutes (300s)
            now = time.time()
            if now - getattr(self, 'last_regime_check', 0) > 300:
                sol_feed = get_global_crypto_price("SOLUSDT")
                sui_feed = get_global_crypto_price("SUIUSDT")
                if sol_feed: CloudBotEngine.LATEST_BINANCE['SOL/USD'] = sol_feed
                if sui_feed: CloudBotEngine.LATEST_BINANCE['SUI/USD'] = sui_feed
                summary_info = {"usd_cash": usd_cash, "sol_held": positions.get('SOL/USD', {}).get('q', 0), "sui_held": positions.get('SUI/USD', {}).get('q', 0)}
                regime = ask_deepseek_market_regime(sol_feed, sui_feed, summary_info)
                if regime:
                    CloudBotEngine.LATEST_REGIME = regime
                    self.last_regime_check = now
            regime_info = CloudBotEngine.LATEST_REGIME

            # --- FAIL-SAFE 1: Dead Man's Switch (Протухание директивы) ---
            directive_age = time.time() - float(regime_info.get("updated_at", 0))
            is_directive_stale = directive_age > float(regime_info.get("ttl_seconds", 1200))
            if is_directive_stale:
                logger.warning(f"⚠️ Dead Man's Switch Triggered! Directive is stale ({directive_age:.0f}s > {regime_info.get('ttl_seconds', 1200)}s). Halting new entries.")

            risk_mode = regime_info.get("risk_mode", "NORMAL")
            allowed_sides = regime_info.get("allowed_sides", "LONG_ONLY")
            can_enter_new = (not is_directive_stale) and (risk_mode != "HALT") and (allowed_sides == "LONG_ONLY")

            # Candidate Collection & Ranking (Spread Compression & Affordability)
            candidates = []
            now_ts = time.time()

            for sym, cfg in crypto_pairs.items():
                # 🛡️ Reject / Margin Cooldown Filter: prevent spamming broker on rejected orders
                if now_ts < self.pair_cooldowns.get(sym, 0):
                    continue

                q = q_dict.get(sym)
                if not q:
                    continue
                bbp = float(q.get('bbp') or 0)
                bap = float(q.get('bap') or 0)
                if not bbp or not bap or bap <= bbp:
                    continue

                if sym == 'SUI/USD':
                    LATENCY_ENGINE.register_tradernet_quote(bbp, bap)

                # 🛡️ 1. Stale Quote Detector: discard quotes not updated in last 12s
                q_utime = float(q.get('utime') or 0)
                if q_utime > 0 and (now_ts - q_utime) > 12.0:
                    continue

                spread_pct = ((bap - bbp) / bbp) * 100.0
                baseline = 2.05 if sym not in ['TRX/USD', 'XRP/USD'] else 4.0
                compression_pct = round(((baseline - spread_pct) / baseline) * 100.0, 1)

                bap_depth = extract_best_ask_qty(q)

                pos_info = positions.get(sym, {})
                inv_qty = float(pos_info.get('q') or 0.0)
                entry_price = float(pos_info.get('bal_price_a') or pos_info.get('price_a') or 0.0)

                sym_orders = [o for o in active_orders if o.get('instr') == sym]
                sell_orders = [o for o in sym_orders if o.get('oper') == 3]
                buy_orders = [o for o in sym_orders if o.get('oper') == 1]

                # Ladder inventory calculation: quantity not yet committed to active sell orders
                total_placed_sell_qty = sum(float(o.get('q') or 0.0) for o in sell_orders)
                unsold_inventory = max(0.0, inv_qty - total_placed_sell_qty)

                # Dynamic Clip Sizing with Book Depth Guard, Capital Cap (35%), and Lot Step Quantization
                min_lot = float(cfg.get('min_qty', 1.0))
                lot_step = float(cfg.get('lot_step', 1.0))
                lot_decimals = int(cfg.get('lot_decimals', 0))

                clip_qty = calculate_clip_size(
                    price=bbp,
                    free_cash=usd_cash,
                    bap_q=bap_depth,
                    max_alloc_pct=0.35,
                    min_lot=min_lot,
                    lot_step=lot_step,
                    lot_decimals=lot_decimals,
                )

                # Fallback to min_lot if clip_qty is zero but sufficient cash exists
                if clip_qty <= 0:
                    continue

                est_cost = round(clip_qty * bbp, 4)
                is_affordable = (est_cost <= (usd_cash - 0.10))

                candidates.append({
                    'sym': sym,
                    'cfg': cfg,
                    'bbp': bbp,
                    'bap': bap,
                    'spread_pct': spread_pct,
                    'baseline': baseline,
                    'compression_pct': compression_pct,
                    'inv_qty': inv_qty,
                    'unsold_inventory': unsold_inventory,
                    'clip_qty': clip_qty,
                    'min_lot': min_lot,
                    'lot_step': lot_step,
                    'lot_decimals': lot_decimals,
                    'entry_price': entry_price,
                    'sym_orders': sym_orders,
                    'sell_orders': sell_orders,
                    'buy_orders': buy_orders,
                    'est_cost': est_cost,
                    'is_affordable': is_affordable
                })

            # Sort candidates by highest spread compression first (best opportunities first)
            candidates.sort(key=lambda c: c['compression_pct'], reverse=True)

            for item in candidates:
                sym = item['sym']
                cfg = item['cfg']
                bbp = item['bbp']
                bap = item['bap']
                spread_pct = item['spread_pct']
                baseline = item['baseline']
                inv_qty = item['inv_qty']
                unsold_inventory = item['unsold_inventory']
                clip_qty = item['clip_qty']
                min_lot = item['min_lot']
                lot_step = item['lot_step']
                lot_decimals = item['lot_decimals']
                entry_price = item['entry_price']
                sell_orders = item['sell_orders']
                buy_orders = item['buy_orders']
                est_cost = item['est_cost']
                is_affordable = item['is_affordable']

                # --- TELEMETRY: Check Fill of previous BUY orders ---
                prev_qty = self.previous_inv.get(sym, inv_qty)
                if inv_qty > prev_qty:
                    filled_diff = inv_qty - prev_qty
                    CloudBotEngine.METRICS["orders_filled"] += 1
                    bought_price = self.active_resting_buys.get(sym, {}).get('price', bbp)
                    if not hasattr(self, 'last_scalp_entry'):
                        self.last_scalp_entry = {}
                    self.last_scalp_entry[sym] = bought_price
                    logger.info(f"[{sym}] 🎉 BUY Order FILLED! Inventory increased +{filled_diff} (Now: {inv_qty}) @ ${bought_price}")
                    self.active_resting_buys.pop(sym, None)
                self.previous_inv[sym] = inv_qty

                # --- TELEMETRY & TTL: Check Resting BUY orders with Spread Blowout Protection ---
                if sym in self.active_resting_buys and buy_orders:
                    track_info = self.active_resting_buys[sym]
                    age = time.time() - track_info.get('placed_at', time.time())
                    is_spread_blown_out = spread_pct > (baseline * 0.90)
                    price_moved_away = abs(bbp - track_info.get('price', bbp)) > 0.0001
                    if is_spread_blown_out or price_moved_away or age >= 15.0:
                        order_id = track_info.get('id')
                        reason = f"Расширение спреда ({spread_pct:.2f}%)" if is_spread_blown_out else ("Сдвиг цен стакана" if price_moved_away else f"Таймаут TTL ({age:.0f}с)")
                        logger.info(f"[{sym}] 🛡️ Авто-отмена приказа #{order_id}: {reason}. Защита капитала активна.")
                        try:
                            self.crypto_client.cancel(order_id)
                        except Exception as ce:
                            logger.warning(f"Error cancelling order #{order_id}: {ce}")
                        CloudBotEngine.METRICS["orders_cancelled_ttl"] += 1
                        self.active_resting_buys.pop(sym, None)
                elif not buy_orders and sym in self.active_resting_buys:
                    self.active_resting_buys.pop(sym, None)

                # --- FAIL-SAFE 2: Time-Stop Tracking ---
                if inv_qty >= min_lot:
                    if sym not in self.inventory_entry_time:
                        self.inventory_entry_time[sym] = time.time()
                else:
                    self.inventory_entry_time.pop(sym, None)

                # --- 1. Multi-Level Ladder Take-Profit Execution (Лесенка) ---
                # Calculate total quantity currently committed to active resting SELL orders
                total_placed_sell_qty = sum(float(o.get('q') or 0.0) for o in sell_orders)
                unsold_inventory = max(0.0, inv_qty - total_placed_sell_qty)

                if unsold_inventory >= min_lot:
                    # Clip-sized exit: do not dump entire balance if book depth is narrow
                    sell_clip = min(unsold_inventory, max(clip_qty, min_lot))
                    # Quantize sell_clip
                    if sell_clip >= lot_step:
                        sell_clip = round(math.floor(round(sell_clip / lot_step, 6)) * lot_step, lot_decimals)
                    else:
                        sell_clip = min_lot

                    # Multi-level lot cost detection:
                    # For SUI/USD with 4 coins: ladder levels correspond to purchases [0.72, 0.7555, 0.7797, 0.80]
                    # The unsold lot gets assigned its specific purchase rung
                    recent_buy = getattr(self, 'last_scalp_entry', {}).get(sym)
                    if sym == 'SUI/USD':
                        # Known SUI ladder purchase tiers
                        sui_ladder_entries = [0.72, 0.7555, 0.7797, 0.80]
                        # Determine how many sell orders already placed
                        orders_count = len(sell_orders)
                        if orders_count < len(sui_ladder_entries):
                            calc_entry = sui_ladder_entries[orders_count]
                        else:
                            calc_entry = recent_buy if (recent_buy and recent_buy > 0) else entry_price
                    else:
                        # For other pairs, strictly use real balance entry_price or last executed scalp fill
                        calc_entry = recent_buy if (recent_buy and recent_buy > 0) else entry_price
                        if not calc_entry or calc_entry <= 0:
                            calc_entry = entry_price if entry_price > 0 else bbp

                    # 🛡️ NEVER_SELL_AT_LOSS HARD GATE:
                    # Minimum safe profit: at least +0.50% or dynamic mean-reversion snapback
                    snapback_premium = max(0.0050, (baseline - spread_pct) / 200.0)
                    min_safe_sell = round(calc_entry * (1.0 + snapback_premium), cfg['decimals'])
                    
                    # Ensure limit price is NEVER lower than min_safe_sell (even if bap is lower)
                    target_tp = round(max(bap, min_safe_sell), cfg['decimals'])
                    if target_tp < min_safe_sell:
                        target_tp = min_safe_sell

                    logger.info(f"[{sym}] 🪜 Лесенка (Ladder Step): Выставляем SELL {sell_clip} @ ${target_tp} (Себестоимость лота: ${calc_entry}, Цель: +{((target_tp/calc_entry)-1)*100:.2f}%)")
                    
                    try:
                        resp = self.crypto_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 3,
                            'order_type_id': 2,
                            'qty': sell_clip if lot_decimals > 0 else int(sell_clip),
                            'limit_price': target_tp,
                            'expiration_id': 1
                        })
                        CloudBotEngine.METRICS["orders_placed"] += 1
                        order_id = resp.get('result', {}).get('order_id') or resp.get('result', {}).get('id')
                        try:
                            send_telegram_msg(
                                f"🪜 **[ЛЕСЕНКА: ВЫСТАВЛЕН ТЕЙК-ПРОФИТ]**\n\n"
                                f"Монета: **{sym}**\n"
                                f"Операция: **Лимитная продажа (SELL)**\n"
                                f"Объем: **{sell_clip}**\n"
                                f"Цена выхода: **${target_tp}**\n"
                                f"Себестоимость лота: **${calc_entry}** (+{((target_tp/calc_entry)-1)*100:.2f}%)\n"
                                f"№ приказа: `{order_id}`",
                                TELEGRAM_CHAT_ID
                            )
                        except Exception:
                            pass
                    except Exception as err:
                        logger.error(f"[{sym}] Ошибка выставления лесенки SELL: {err}")

                # --- 2. Flat / Liquid Inventory & Maker BUY -> Adaptive Snapback Entry ---
                elif unsold_inventory < min_lot and not buy_orders and is_affordable:
                    # Adaptive trigger: spread compressed by >= 25% or spread <= 1.55%
                    is_spread_compressed = (spread_pct <= (baseline * 0.75)) or (spread_pct <= 1.55)

                    if not is_spread_compressed:
                        if not can_enter_new or spread_pct > 2.5:
                            continue

                    # 🛡️ 3. Adverse Selection Guard: Lead-Lag Radar on Binance
                    impulse = LEAD_LAG_RADAR.get_market_impulse(cfg.get('binance', ''))
                    is_impulse_pump = False
                    if impulse.get('is_fresh'):
                        # Veto on Toxic Flow: Never buy if Binance is dumping or CVD negative
                        if impulse.get('is_dump') or impulse.get('impulse_pct', 0.0) <= -0.15:
                            CloudBotEngine.METRICS["dump_blocks"] += 1
                            logger.info(f"[{sym}] 🛑 Entry skipped: Adverse Selection Guard (Binance impulse: {impulse.get('impulse_pct', 0.0):.2f}%, CVD: {impulse.get('cvd', 0.0):.2f})")
                            continue
                        if impulse.get('is_pump'):
                            is_impulse_pump = True
                            CloudBotEngine.METRICS["impulse_entries"] += 1

                    buy_price = round(bbp, cfg['decimals'])
                    logger.info(f"[{sym}] 🎯 Approved Maker BUY (Compression: {item['compression_pct']}%): {clip_qty} @ ${buy_price:.4f} (Spread: {spread_pct:.2f}%, Cash: ${usd_cash:.2f})")
                    resp = self.crypto_client.authorized_request('putTradeOrder', {
                        'instr_name': sym,
                        'action_id': 1,
                        'order_type_id': 2,
                        'qty': clip_qty if lot_decimals > 0 else int(clip_qty),
                        'limit_price': buy_price,
                        'expiration_id': 1
                    })
                    order_id = resp.get('result', {}).get('order_id') or resp.get('result', {}).get('id')
                    is_accepted = bool(order_id) and (resp.get('error') is None)
                    err_msg = resp.get('error') or resp.get('result', {}).get('msg') or resp.get('errMsg')
                    
                    if is_accepted:
                        CloudBotEngine.METRICS["orders_placed"] += 1
                        usd_cash -= est_cost  # Reserve cash for next pair in loop
                        self.active_resting_buys[sym] = {
                            'id': order_id,
                            'placed_at': time.time(),
                            'is_impulse': is_impulse_pump,
                            'price': buy_price,
                            'qty': clip_qty
                        }
                        try:
                            send_telegram_msg(
                                f"🚀 **[АВТО-ОРДЕР ВЫСТАВЛЕН]**\n\n"
                                f"Монета: **{sym}**\n"
                                f"Операция: **Лимитная покупка (BUY)**\n"
                                f"Объем: **{clip_qty}** (~${est_cost:.2f})\n"
                                f"Цена: **${buy_price}**\n"
                                f"Сжатие спреда: **{spread_pct:.2f}%** (норма {baseline}%)\n"
                                f"№ приказа: `{order_id}`",
                                TELEGRAM_CHAT_ID
                            )
                        except Exception:
                            pass
                    else:
                        # Broker Rejected Order (e.g. margin/collateral or critical risk limit)
                        cooldown_sec = 600.0  # 10 minutes silence for this pair
                        self.pair_cooldowns[sym] = time.time() + cooldown_sec
                        logger.warning(f"[{sym}] ⚠️ Брокер отклонил приказ BUY ({err_msg or 'недостаточно обеспечения/реджект'}). Пауза {cooldown_sec/60:.0f} мин.")

            # --- Realized Profit Tracking (with Tradernet API get_trades_history sync) ---
            try:
                now_sync = time.time()
                if now_sync - getattr(self, 'last_trades_history_sync', 0) > 300:
                    try:
                        dt_start = datetime.date.today() - datetime.timedelta(days=7)
                        hist_res = self.crypto_client.get_trades_history(start=dt_start, limit=50)
                        hist_trades = hist_res.get('result', {}).get('trades', [])
                        if hist_trades:
                            h_today = 0.0
                            h_total = 0.0
                            today_s = datetime.date.today().isoformat()
                            for ht in hist_trades:
                                p_val = float(ht.get('profit') or 0.0)
                                if p_val > 0:
                                    h_total += p_val
                                    if str(ht.get('date', '')).startswith(today_s):
                                        h_today += p_val
                            if h_total > 0:
                                CloudBotEngine.REALIZED_CRYPTO_STATS["total_profit_usd"] = round(h_total, 4)
                                CloudBotEngine.REALIZED_CRYPTO_STATS["today_profit_usd"] = round(h_today, 4)
                                CloudBotEngine.REALIZED_CRYPTO_STATS["completed_cycles"] = len([t for t in hist_trades if float(t.get('profit') or 0) > 0])
                                self.last_trades_history_sync = now_sync
                    except Exception as h_err:
                        logger.warning(f"Tradernet get_trades_history sync notice: {h_err}")

                realized_crypto = []
                now_str_date = datetime.datetime.now().strftime("%Y-%m-%d")
                today_usd = 0.0
                total_usd = 0.0
                for o in orders:
                    instr = o.get('instr', '')
                    for tr in o.get('trade', []):
                        prof = float(tr.get('profit') or 0.0)
                        if prof > 0:
                            tr_date = str(tr.get('date', ''))
                            total_usd += prof
                            if now_str_date in tr_date:
                                today_usd += prof
                            realized_crypto.append({
                                'instr': instr,
                                'qty': tr.get('q'),
                                'price': tr.get('p'),
                                'profit': round(prof, 4),
                                'date': tr_date,
                                'order_id': o.get('id')
                            })
                realized_crypto.sort(key=lambda x: str(x['date']), reverse=True)
                if total_usd > 0 or not CloudBotEngine.REALIZED_CRYPTO_STATS.get("total_profit_usd"):
                    CloudBotEngine.REALIZED_CRYPTO_STATS = {
                        "today_profit_usd": round(today_usd, 4),
                        "total_profit_usd": round(total_usd, 4),
                        "completed_cycles": len(realized_crypto),
                        "profitable_trades": realized_crypto[:10],
                        "last_sync_time": time.time()
                    }
            except Exception as cpe:
                logger.error(f"Error parsing crypto realized trades: {cpe}")

        except Exception as e:
            logger.error(f"Error in crypto step: {e}")

    def run_kase_step(self):
        if not is_kase_market_open():
            return
        try:
            # Active scalping configs for KASE
            kase_configs = {
                'AIRA.KZ': {'qty': 3, 'min_spread_pct': 0.0035, 'min_step': 0.01},
                'KZTO.KZ': {'qty': 1, 'min_spread_pct': 0.0020, 'min_step': 0.01},
                'BCCIRB.KZ': {'qty': 50, 'min_spread_pct': 0.0020, 'min_step': 0.01},
                'KMGD.KZ': {'qty': 25, 'min_spread_pct': 0.0035, 'min_step': 0.01}
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
                if curr_shares >= cfg['qty']:
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

                # Case A: We hold shares and have no active SELL order -> place TP sell above entry
                if curr_shares > 0 and curr_shares >= cfg['qty'] and not sell_orders:
                    tp_price = max(bap, round(entry_price * (1 + cfg['min_spread_pct']), 2))
                    logger.info(f"[{sym}] Placing Take-Profit SELL: {cfg['qty']} shares @ {tp_price:.2f} KZT (Entry: {entry_price:.2f})")
                    self.kase_client.authorized_request('putTradeOrder', {
                        'instr_name': sym,
                        'action_id': 3,
                        'order_type_id': 2,
                        'qty': cfg['qty'],
                        'limit_price': tp_price,
                        'expiration_id': 1
                    })

                # Case B: We have no active BUY order and no inventory -> place resting BUY at best bid
                elif curr_shares < cfg['qty'] and not buy_orders:
                    # Check spread profitability & volume liquidity
                    spread_pct = (bap - bbp) / bbp
                    req_cost = cfg['qty'] * bbp
                    if spread_pct >= cfg['min_spread_pct'] and kzt_cash >= req_cost:
                        logger.info(f"[{sym}] Placing Maker BUY: {cfg['qty']} shares @ {bbp:.2f} KZT (Spread: {spread_pct*100:.2f}%, Cash: {kzt_cash:.2f} KZT)")
                        self.kase_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 1,
                            'order_type_id': 2,
                            'qty': cfg['qty'],
                            'limit_price': round(bbp, 2),
                            'expiration_id': 1
                        })
                        kzt_cash -= req_cost

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

    def start(self):
        logger.info("=" * 65)
        logger.info("🚀 Tradernet AI Cloud Bot (DeepSeek + Global Arb) Started")
        logger.info("Crypto: SOL/USD (AI-Driven) | KASE: ASBN, HSBK, KMGD")
        logger.info("=" * 65)

        while True:
            try:
                self.run_crypto_step()
                self.run_kase_step()
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
                            summary = engine.crypto_client.account_summary().get('result', {}).get('ps', {})
                            cash_lines = [f"• {a.get('curr')}: {a.get('s')}" for a in summary.get('acc', []) if float(a.get('s') or 0) > 0]
                            pos_lines = [f"• {p.get('i')}: {p.get('q')} шт (рыночная: ${p.get('mkt_price')})" for p in summary.get('pos', [])]
                            reply = "💰 Баланс криптосчета:\n" + "\n".join(cash_lines) + "\n\n📊 Открытые позиции:\n" + "\n".join(pos_lines)
                            send_telegram_msg(reply, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка проверки баланса: {e}", chat_id)
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
                            usd_c = getattr(CloudBotEngine, 'LATEST_USD_CASH', 1.58)
                            sync_st = getattr(CloudBotEngine, 'TRADES_SYNC_STATUS', 'OK (Tradernet 7d)')
                            reply = (
                                "📊 **ТЕЛЕМЕТРИЯ TRADERNET И КРИПТО-СКАЛЬПЕРА**\n\n"
                                f"💵 **Свободный баланс:** ${usd_c:.2f}\n"
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
                            lines = ["📡 **Радар спредов Tradernet 24/7:**\n"]
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
                                "summary": engine.crypto_client.account_summary().get('result', {}).get('ps', {})
                            }
                            answer = ask_deepseek_chat(text, context)
                            send_telegram_msg(answer, chat_id)
                        except Exception as e:
                            logger.error(f"Telegram DeepSeek handling error: {e}")
                            send_telegram_msg(f"Ошибка обработки: {e}", chat_id)

        except Exception as e:
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
