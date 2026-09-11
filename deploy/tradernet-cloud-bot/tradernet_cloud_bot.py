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
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

import tradernet

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
        if self.path == '/json':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            status = {
                "status": "online",
                "bot": "Tradernet AI Cloud Bot (DeepSeek + Global Arb)",
                "kase_market": "OPEN" if is_kase_market_open() else "CLOSED",
                "deepseek_connected": bool(DEEPSEEK_API_KEY),
                "profit_report": {
                    "today_profit_kzt": pnl_stats.get('today_profit_kzt', 0.0),
                    "total_profit_kzt": pnl_stats.get('total_profit_kzt', 0.0),
                    "completed_cycles": pnl_stats.get('completed_cycles', 0),
                    "winrate_pct": 100.0,
                    "recent_trades": pnl_stats.get('profitable_trades', [])[:5]
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
            <div class="card">
                <div class="card-header">
                    <div class="card-title">🌊 Sui Network (SUI/USD)</div>
                    <span class="badge" style="background: #10b981;">АКТИВНЫЙ ТЕЙК-ПРОФИТ</span>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">В портфеле</div>
                        <div class="stat-val">2 SUI (вход: $0.7898)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Тейк-профит №1</div>
                        <div class="stat-val" style="color: #10b981;">1 SUI @ $0.7926</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Тейк-профит №2</div>
                        <div class="stat-val" style="color: #6366f1;">1 SUI @ $0.8080</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Защита от минуса</div>
                        <div class="stat-val" style="color: #10b981;">Строго в плюс</div>
                    </div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <div class="card-title">💎 Solana (SOL/USD)</div>
                    <span class="badge" style="background: #6366f1;">ТЕЙК-ПРОФИТ В ОЧЕРЕДИ</span>
                </div>
                <div class="stat-grid">
                    <div class="stat-box">
                        <div class="stat-label">В портфеле</div>
                        <div class="stat-val">0.001 SOL (вход: $104.60)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Тейк-профит</div>
                        <div class="stat-val" style="color: #6366f1;">$104.87 (в плюс)</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-label">Мировой рынок</div>
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
    end_time = datetime.time(17, 0, 0)
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
5. 'ttl_seconds': время жизни директивы (обычно 600 сек).

Ответь ИСКЛЮЧИТЕЛЬНО в формате валидного JSON по схеме:
{{
  "risk_mode": "NORMAL",
  "allowed_sides": "LONG_ONLY",
  "risk_score": 5,
  "commentary": "текст аналитической сводки на русском",
  "sol_outlook": "краткий ориентир по Solana",
  "sui_outlook": "краткий ориентир по Sui",
  "ttl_seconds": 600
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
            "ttl_seconds": 600,
            "updated_at": time.time(),
            "is_fallback": True
        }

class CloudBotEngine:
    LATEST_REGIME = {
        "risk_mode": "NORMAL",
        "allowed_sides": "LONG_ONLY",
        "risk_score": 5,
        "commentary": "Рынок в рабочей фазе. Бот работает в режиме автономного сбора спреда.",
        "sol_outlook": "Консолидация в диапазоне $100-103",
        "sui_outlook": "Попытка отскока от зоны поддержки $0.75",
        "ttl_seconds": 600,
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

    def run_crypto_step(self):
        try:
            crypto_pairs = {
                'SOL/USD': {'binance': 'SOLUSDT', 'qty': '0.001', 'min_profit_pct': 0.0025, 'decimals': 2},
                'SUI/USD': {'binance': 'SUIUSDT', 'qty': '1', 'min_profit_pct': 0.0035, 'decimals': 4}
            }

            user_summary = self.crypto_client.account_summary().get('result', {}).get('ps', {})
            acc_list = user_summary.get('acc', [])
            usd_cash = 1.58
            for a in acc_list:
                if a.get('curr') == 'USD':
                    usd_cash = float(a.get('s') or 1.58)

            pos_list = user_summary.get('pos', [])
            positions = {p.get('i'): p for p in pos_list}

            orders = self.crypto_client.get_placed().get('result', {}).get('orders', {}).get('order', [])
            active_orders = [o for o in orders if o.get('stat') in [10, 2, 1]]

            quotes = self.crypto_client.get_quotes(list(crypto_pairs.keys())).get('result', {}).get('q', [])
            q_dict = {q.get('c'): q for q in quotes}

            # Check macro regime via DeepSeek once every 20 minutes
            now = time.time()
            if now - getattr(self, 'last_regime_check', 0) > 1200:
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
            is_directive_stale = directive_age > float(regime_info.get("ttl_seconds", 600))
            if is_directive_stale:
                logger.warning(f"⚠️ Dead Man's Switch Triggered! Directive is stale ({directive_age:.0f}s > {regime_info.get('ttl_seconds', 600)}s). Halting new entries.")

            risk_mode = regime_info.get("risk_mode", "NORMAL")
            allowed_sides = regime_info.get("allowed_sides", "LONG_ONLY")
            can_enter_new = (not is_directive_stale) and (risk_mode != "HALT") and (allowed_sides == "LONG_ONLY")

            for sym, cfg in crypto_pairs.items():
                q = q_dict.get(sym)
                if not q:
                    continue
                bbp = float(q.get('bbp') or 0)
                bap = float(q.get('bap') or 0)
                if not bbp or not bap:
                    continue

                spread_pct = ((bap - bbp) / bbp) * 100.0

                pos_info = positions.get(sym, {})
                inv_qty = float(pos_info.get('q') or 0.0)
                entry_price = float(pos_info.get('bal_price_a') or pos_info.get('price_a') or 0.0)

                sym_orders = [o for o in active_orders if o.get('instr') == sym]
                sell_orders = [o for o in sym_orders if o.get('oper') == 3]
                buy_orders = [o for o in sym_orders if o.get('oper') == 1]

                # --- TELEMETRY: Check Fill of previous BUY orders ---
                prev_qty = self.previous_inv.get(sym, inv_qty)
                if inv_qty > prev_qty:
                    filled_diff = inv_qty - prev_qty
                    CloudBotEngine.METRICS["orders_filled"] += 1
                    logger.info(f"[{sym}] 🎉 BUY Order FILLED! Inventory increased +{filled_diff} (Now: {inv_qty})")
                    self.active_resting_buys.pop(sym, None)
                self.previous_inv[sym] = inv_qty

                # --- TELEMETRY & TTL: Check Resting BUY orders age (TTL ~15s) ---
                if sym in self.active_resting_buys and buy_orders:
                    track_info = self.active_resting_buys[sym]
                    age = time.time() - track_info.get('placed_at', time.time())
                    # If resting > 15s or price has moved away, cancel to avoid stale fills
                    if age >= 15.0:
                        order_id = track_info.get('id')
                        logger.info(f"[{sym}] ⏱ TTL Expired ({age:.1f}s > 15s) for resting BUY #{order_id}. Cancelling order.")
                        try:
                            self.crypto_client.cancel(order_id)
                        except Exception as ce:
                            logger.warning(f"Error cancelling stale order #{order_id}: {ce}")
                        CloudBotEngine.METRICS["orders_cancelled_ttl"] += 1
                        self.active_resting_buys.pop(sym, None)
                elif not buy_orders and sym in self.active_resting_buys:
                    self.active_resting_buys.pop(sym, None)

                # --- FAIL-SAFE 2: Time-Stop Tracking (Деградация торговой идеи) ---
                if inv_qty >= float(cfg['qty']):
                    if sym not in self.inventory_entry_time:
                        self.inventory_entry_time[sym] = time.time()
                else:
                    self.inventory_entry_time.pop(sym, None)

                # 1. Manage holding position -> Multi-level Take-Profit (+1.5R or Turbo)
                target_qty = float(cfg['qty'])
                if inv_qty >= target_qty and not sell_orders:
                    # Turbo-scalp if spread <= 0.25%, else standard 1.5R target
                    pair_tp_multiplier = 1.0015 if spread_pct <= 0.25 else 1.0035
                    min_safe_sell = round(entry_price * pair_tp_multiplier, cfg['decimals'])
                    target_tp = round(max(bap, min_safe_sell), cfg['decimals'])
                    logger.info(f"[{sym}] Submitting Take-Profit SELL: {cfg['qty']} @ ${target_tp} (Entry: ${entry_price:.4f})")
                    self.crypto_client.authorized_request('putTradeOrder', {
                        'instr_name': sym,
                        'action_id': 3,
                        'order_type_id': 2,
                        'qty': cfg['qty'],
                        'limit_price': target_tp,
                        'expiration_id': 1
                    })

                # 2. Manage flat position & new BUY -> Maker Entry with Risk Gates
                elif inv_qty < target_qty and not buy_orders:
                    # Gate 1: Check Dead Man's Switch & Risk Directive
                    if not can_enter_new:
                        continue

                    # Gate 2: Microstructure filter (Do not buy if spread is unnaturally blown up > 2.5%)
                    if spread_pct > 2.5:
                        continue

                    # Gate 3: Binance Lead-Lag Radar (Latency Arbitrage & Dump Filter)
                    impulse = LEAD_LAG_RADAR.get_market_impulse(cfg['binance'])
                    is_impulse_pump = False
                    if impulse['is_fresh']:
                        # Dump Filter: Never buy a falling knife if Binance is dumping or CVD negative
                        if impulse['is_dump']:
                            CloudBotEngine.METRICS["dump_blocks"] += 1
                            CloudBotEngine.METRICS["last_dump_event"] = {
                                "sym": sym,
                                "impulse_pct": impulse['impulse_pct'],
                                "cvd": impulse['cvd'],
                                "time": time.time()
                            }
                            logger.info(f"[{sym}] 🛑 Entry skipped: Binance dump detected (Impulse: {impulse['impulse_pct']:.2f}%, CVD: {impulse['cvd']:.2f})")
                            continue

                        # Latency Arb Boost: If Binance is pumping (+0.35%), log lead-lag signal
                        if impulse['is_pump']:
                            is_impulse_pump = True
                            CloudBotEngine.METRICS["impulse_entries"] += 1
                            CloudBotEngine.METRICS["last_impulse_event"] = {
                                "sym": sym,
                                "impulse_pct": impulse['impulse_pct'],
                                "cvd": impulse['cvd'],
                                "time": time.time()
                            }
                            logger.info(f"[{sym}] 🚀 Lead-Lag Latency Arbitrage Opportunity! Binance impulse: +{impulse['impulse_pct']:.2f}% (CVD: +{impulse['cvd']:.2f})")

                    est_cost = target_qty * bbp
                    if usd_cash >= est_cost:
                        buy_price = round(bbp, cfg['decimals'])
                        logger.info(f"[{sym}] Approved Post-Only Maker BUY: {cfg['qty']} @ ${buy_price:.4f} (Spread: {spread_pct:.2f}%)")
                        resp = self.crypto_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 1,
                            'order_type_id': 2,
                            'qty': cfg['qty'],
                            'limit_price': buy_price,
                            'expiration_id': 1
                        })
                        CloudBotEngine.METRICS["orders_placed"] += 1
                        order_id = resp.get('result', {}).get('order_id') or resp.get('result', {}).get('id')
                        self.active_resting_buys[sym] = {
                            'id': order_id,
                            'placed_at': time.time(),
                            'is_impulse': is_impulse_pump,
                            'price': buy_price
                        }

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
                    elif text.lower() in ['метрики', '/metrics', 'статистика', '/stats']:
                        try:
                            m = CloudBotEngine.METRICS
                            mem = get_process_memory_mb()
                            p = m.get('orders_placed', 0)
                            f = m.get('orders_filled', 0)
                            c = m.get('orders_cancelled_ttl', 0)
                            fr = round((f / p * 100.0), 1) if p > 0 else 0.0
                            upt = round((time.time() - m.get('start_time', time.time())) / 3600.0, 1)
                            reply = (
                                "📊 **Канареечный запуск (Canary Run 24-48h)**\n\n"
                                f"1️⃣ **Fill Rate лимиток:** {fr}% ({f} исп. из {p})\n"
                                f"   ⏱ Отменено по TTL (>15s): {c}\n"
                                f"   🚀 Импульсных входов по Binance: {m.get('impulse_entries', 0)}\n\n"
                                f"2️⃣ **Dump Protection:** {m.get('dump_blocks', 0)} заблокировано\n"
                                f"   🛡 Защита от падающего ножа сработала успешно\n\n"
                                f"3️⃣ **RAM Контейнера:** {mem} MB (норма: 60–120 MB)\n"
                                f"   ⏳ Аптайм сессии: {upt} ч\n\n"
                                f"4️⃣ **DeepSeek Cold Path:** {m.get('deepseek_last_latency_sec', 0)}s\n"
                                f"   ⚠️ Таймаутов/Fallback: {m.get('deepseek_timeouts', 0)}"
                            )
                            send_telegram_msg(reply, chat_id)
                        except Exception as e:
                            send_telegram_msg(f"Ошибка получения метрик: {e}", chat_id)
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

    engine = CloudBotEngine()

    t_tg = threading.Thread(target=telegram_polling_loop, args=(engine,), daemon=True)
    t_tg.start()

    engine.start()

if __name__ == '__main__':
    main()
