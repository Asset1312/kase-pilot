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

def ask_deepseek_solana(binance_data: dict, freedom_quote: dict, sol_inventory: float) -> dict:
    """DeepSeek AI Market Regime & Spread Arbitrage Consultant."""
    if not DEEPSEEK_API_KEY:
        return {}
    url = "https://api.deepseek.com/chat/completions"
    prompt = f"""
You are an advanced HFT crypto quant trading Solana (SOL/USD) on Freedom Broker (CR725726).
Market Situation:
- Global Real-Time Benchmark (Binance): {binance_data}
- Freedom Broker Local Quote: {freedom_quote}
- Current Inventory: {sol_inventory} SOL
- Account Cash: $1.58 USD

Key Context:
- Freedom Broker has a wide synthetic OTC spread (~2.1%).
- Broker commission is 0.00$ (FREE).
- We have 10-second lead-lag edge from Binance real-time price.

Task:
1. Determine market momentum (Bullish/Bearish/Neutral).
2. If we hold 0.001 SOL, recommend exact profitable sell price.
3. If flat, decide if BUY signal is safe (do NOT buy during dumps or falling knife).

Respond ONLY with valid JSON in this exact schema:
{{
  "action": "BUY" or "SELL" or "HOLD" or "WAIT",
  "reasoning": "brief 1-2 sentence explanation in Russian",
  "recommended_buy_price": 102.50,
  "recommended_sell_price": 104.85,
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
        logger.error(f"DeepSeek call error: {e}")
    return {}

class CloudBotEngine:
    LATEST_ADVICE = {}
    LATEST_BINANCE = {}

    def __init__(self):
        self.kase_client = tradernet.Tradernet(KASE_PUB_KEY, KASE_SEC_KEY)
        self.crypto_client = tradernet.Tradernet(CRYPTO_PUB_KEY, CRYPTO_SEC_KEY)
        self.last_ai_check = 0
        self.cached_ai_advice = {}

    def run_crypto_step(self):
        try:
            quotes = self.crypto_client.get_quotes(['SOL/USD']).get('result', {}).get('q', [])
            if not quotes:
                return
            q = quotes[0]
            bbp = float(q.get('bbp') or 0)
            bap = float(q.get('bap') or 0)
            if not bbp or not bap:
                return

            # Check inventory
            pos = self.crypto_client.get_user_data().get('OPQ', {}).get('ps', {}).get('pos', [])
            sol_qty = 0.0
            sol_entry = 104.60
            for p in pos:
                if p.get('i') == 'SOL/USD':
                    sol_qty = float(p.get('q') or 0.0)
                    sol_entry = float(p.get('bal_price_a') or p.get('price_a') or 104.60)

            # Check open orders
            orders = self.crypto_client.get_placed().get('result', {}).get('orders', {}).get('order', [])
            sol_sell_id = None
            sol_buy_id = None
            for o in orders:
                if o.get('instr') == 'SOL/USD':
                    if o.get('oper') == 3:
                        sol_sell_id = o.get('id')
                    elif o.get('oper') == 1:
                        sol_buy_id = o.get('id')

            # Consult DeepSeek + Global Binance every 45 seconds
            now = time.time()
            if now - self.last_ai_check > 45:
                global_sol = get_global_binance_price("SOLUSDT")
                if global_sol:
                    CloudBotEngine.LATEST_BINANCE = global_sol
                freedom_snapshot = {"bid": bbp, "ask": bap, "spread": round(bap - bbp, 2)}
                advice = ask_deepseek_solana(global_sol, freedom_snapshot, sol_qty)
                if advice:
                    self.cached_ai_advice = advice
                    CloudBotEngine.LATEST_ADVICE = advice
                    self.last_ai_check = now
                    logger.info(f"🧠 DeepSeek AI Signal: {advice.get('action')} | Reason: {advice.get('reasoning')}")

            ai_action = self.cached_ai_advice.get("action", "HOLD")

            # 1. Manage holding position
            if sol_qty >= 0.001 and not sol_sell_id:
                rec_sell = self.cached_ai_advice.get("recommended_sell_price")
                min_safe_sell = round(sol_entry * 1.0025, 2)
                target_tp = max(rec_sell or bap, min_safe_sell)
                logger.info(f"[SOL/USD] Submitting Take-Profit SELL: 0.001 SOL @ ${target_tp:.2f} (Entry: ${sol_entry:.2f})")
                self.crypto_client.authorized_request('putTradeOrder', {
                    'instr_name': 'SOL/USD',
                    'action_id': 3,
                    'order_type_id': 2,
                    'qty': '0.001',
                    'limit_price': target_tp,
                    'expiration_id': 1
                })
                return

            # 2. Manage flat position & new buy
            if sol_qty < 0.001 and not sol_buy_id:
                if ai_action == "BUY":
                    rec_buy = self.cached_ai_advice.get("recommended_buy_price", bbp)
                    buy_price = round(min(rec_buy, bbp), 2)
                    logger.info(f"[SOL/USD] DeepSeek Approved BUY! Submitting 0.001 SOL @ ${buy_price:.2f}")
                    self.crypto_client.authorized_request('putTradeOrder', {
                        'instr_name': 'SOL/USD',
                        'action_id': 1,
                        'order_type_id': 2,
                        'qty': '0.001',
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
                    # Check spread profitability
                    if (bap - bbp) / bbp >= cfg['min_spread_pct']:
                        logger.info(f"[{sym}] Placing Maker BUY: {cfg['qty']} shares @ {bbp:.2f} KZT")
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
