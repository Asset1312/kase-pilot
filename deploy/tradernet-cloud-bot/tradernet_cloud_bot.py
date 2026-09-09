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
from http.server import HTTPServer, BaseHTTPRequestHandler

import tradernet

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

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        status = {
            "status": "online",
            "bot": "Tradernet AI Cloud Bot (DeepSeek + Global Arb)",
            "service": "Render.com Web Service",
            "kase_market": "OPEN" if is_kase_market_open() else "CLOSED",
            "deepseek_connected": bool(DEEPSEEK_API_KEY),
            "ai_latest_signal": getattr(CloudBotEngine, 'LATEST_ADVICE', {}),
            "latest_binance": getattr(CloudBotEngine, 'LATEST_BINANCE', {}),
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(status, indent=2).encode('utf-8'))

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

def get_global_binance_price(symbol="SOLUSDT") -> dict:
    """Fetch real-time global price from public Binance API."""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=4) as r:
            data = json.loads(r.read())
            return {
                "last_price": float(data['lastPrice']),
                "change_pct": float(data['priceChangePercent']),
                "high_24h": float(data['highPrice']),
                "low_24h": float(data['lowPrice'])
            }
    except Exception as e:
        logger.error(f"Global Binance query error: {e}")
    return {}

def ask_deepseek_crypto(symbol: str, binance_data: dict, freedom_quote: dict, inventory: float, cash: float) -> dict:
    """DeepSeek AI Market Regime & Spread Arbitrage Consultant for Crypto."""
    if not DEEPSEEK_API_KEY:
        return {}
    url = "https://api.deepseek.com/chat/completions"
    prompt = f"""
You are an advanced HFT crypto quant trading {symbol} on Freedom Broker (Account CR725726).
Market Situation:
- Asset: {symbol}
- Global Real-Time Benchmark (Binance): {binance_data}
- Freedom Broker Local Quote: {freedom_quote}
- Current Inventory: {inventory} {symbol}
- Account Cash: ${cash:.2f} USD

Key Context:
- Freedom Broker has a synthetic OTC spread (~2%).
- Broker commission is 0.00$ (FREE).
- We have 10-second lead-lag edge from Binance real-time price.

Task:
1. Determine market momentum (Bullish/Bearish/Neutral).
2. If we hold inventory, recommend exact profitable sell price.
3. If flat, decide if BUY signal is safe (do NOT buy during dumps or falling knife).

Respond ONLY with valid JSON in this exact schema:
{{
  "action": "BUY" or "SELL" or "HOLD" or "WAIT",
  "reasoning": "brief 1-2 sentence explanation in Russian",
  "recommended_buy_price": float,
  "recommended_sell_price": float,
  "risk_score": 1-10
}}
"""
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a disciplined quantitative trader. Always respond in valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            data=json.dumps(payload).encode("utf-8")
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            return json.loads(d["choices"][0]["message"]["content"])
    except Exception as e:
        logger.error(f"DeepSeek call error for {symbol}: {e}")
    return {}

class CloudBotEngine:
    LATEST_ADVICE = {}
    LATEST_BINANCE = {}

    def __init__(self):
        self.kase_client = tradernet.Tradernet(KASE_PUB_KEY, KASE_SEC_KEY)
        self.crypto_client = tradernet.Tradernet(CRYPTO_PUB_KEY, CRYPTO_SEC_KEY)
        self.last_ai_check = {}
        self.cached_ai_advice = {}
        self.inventory_entry_time = {}

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

            for sym, cfg in crypto_pairs.items():
                q = q_dict.get(sym)
                if not q:
                    continue
                bbp = float(q.get('bbp') or 0)
                bap = float(q.get('bap') or 0)
                if not bbp or not bap:
                    continue

                pos_info = positions.get(sym, {})
                inv_qty = float(pos_info.get('q') or 0.0)
                entry_price = float(pos_info.get('bal_price_a') or pos_info.get('price_a') or 0.0)

                sym_orders = [o for o in active_orders if o.get('instr') == sym]
                sell_orders = [o for o in sym_orders if o.get('oper') == 3]
                buy_orders = [o for o in sym_orders if o.get('oper') == 1]

                # Consult DeepSeek + Global Binance
                now = time.time()
                last_check = self.last_ai_check.get(sym, 0)
                if now - last_check > 45:
                    global_feed = get_global_binance_price(cfg['binance'])
                    if global_feed:
                        CloudBotEngine.LATEST_BINANCE[sym] = global_feed
                    freedom_snapshot = {"bid": bbp, "ask": bap, "spread": round(bap - bbp, 4)}
                    advice = ask_deepseek_crypto(sym, global_feed, freedom_snapshot, inv_qty, usd_cash)
                    if advice:
                        self.cached_ai_advice[sym] = advice
                        CloudBotEngine.LATEST_ADVICE[sym] = advice
                        self.last_ai_check[sym] = now
                        logger.info(f"🧠 DeepSeek [{sym}]: {advice.get('action')} | Reason: {advice.get('reasoning')}")

                ai_info = self.cached_ai_advice.get(sym, {})
                ai_action = ai_info.get("action", "HOLD")

                # 1. Manage holding position -> TP Sell
                target_qty = float(cfg['qty'])
                if inv_qty >= target_qty and not sell_orders:
                    rec_sell = ai_info.get("recommended_sell_price")
                    min_safe_sell = round(entry_price * (1 + cfg['min_profit_pct']), cfg['decimals'])
                    target_tp = round(max(rec_sell or bap, min_safe_sell), cfg['decimals'])
                    logger.info(f"[{sym}] Submitting Take-Profit SELL: {cfg['qty']} @ ${target_tp} (Entry: ${entry_price:.4f})")
                    self.crypto_client.authorized_request('putTradeOrder', {
                        'instr_name': sym,
                        'action_id': 3,
                        'order_type_id': 2,
                        'qty': cfg['qty'],
                        'limit_price': target_tp,
                        'expiration_id': 1
                    })

                # 2. Manage flat position & new BUY
                elif inv_qty < target_qty and not buy_orders:
                    # Require available cash
                    est_cost = target_qty * bbp
                    if usd_cash >= est_cost and ai_action == "BUY":
                        rec_buy = ai_info.get("recommended_buy_price", bbp)
                        buy_price = round(min(rec_buy, bbp), cfg['decimals'])
                        logger.info(f"[{sym}] DeepSeek Approved BUY! Submitting {cfg['qty']} @ ${buy_price}")
                        self.crypto_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 1,
                            'order_type_id': 2,
                            'qty': cfg['qty'],
                            'limit_price': buy_price,
                            'expiration_id': 1
                        })

        except Exception as e:
            logger.error(f"Error in crypto step: {e}")

    def run_kase_step(self):
        if not is_kase_market_open():
            return
        try:
            # Active scalping configs for KASE
            kase_configs = {
                'AIRA.KZ': {'qty': 3, 'min_spread_pct': 0.0035, 'min_step': 0.01},
                'KMGD.KZ': {'qty': 25, 'min_spread_pct': 0.0035, 'min_step': 0.01}
            }

            user_data = self.kase_client.get_user_data().get('OPQ', {})
            positions = {p.get('i'): p for p in user_data.get('ps', {}).get('pos', [])}
            orders_list = user_data.get('orders', {}).get('order', [])
            active_orders = [o for o in orders_list if o.get('stat') in [10, 2, 1]]

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

                pos_info = positions.get(sym, {})
                curr_shares = int(pos_info.get('q') or 0)
                entry_price = float(pos_info.get('bal_price_a') or pos_info.get('price_a') or 0)

                sym_orders = [o for o in active_orders if o.get('instr') == sym]
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
                if curr_shares >= cfg['qty'] and not sell_orders:
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
                    if spread_pct >= cfg['min_spread_pct']:
                        logger.info(f"[{sym}] Placing Maker BUY: {cfg['qty']} shares @ {bbp:.2f} KZT (Spread: {spread_pct*100:.2f}%)")
                        self.kase_client.authorized_request('putTradeOrder', {
                            'instr_name': sym,
                            'action_id': 1,
                            'order_type_id': 2,
                            'qty': cfg['qty'],
                            'limit_price': round(bbp, 2),
                            'expiration_id': 1
                        })

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

def main():
    t_web = threading.Thread(target=start_health_server, daemon=True)
    t_web.start()

    engine = CloudBotEngine()
    engine.start()

if __name__ == '__main__':
    main()
