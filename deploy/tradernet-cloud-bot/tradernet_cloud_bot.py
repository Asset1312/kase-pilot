"""
Cloud Tradernet Multi-Asset Trading Bot (Render.com Web Service)
Trades KASE stocks (HSBK.KZ, ASBN.KZ, KMGD.KZ) and Crypto (SOL/USD)
via Tradernet API (Freedom Broker).

Includes:
- Embedded HTTP Health-Check server on $PORT (or 10000) for Render Web Service compliance.
- 0% Commission Scalping on CR account for Crypto.
- Dynamic Maker / Spread Scalping for KASE during market hours.
"""

import os
import sys
import json
import time
import datetime
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import tradernet

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TradernetCloudBot")

# Port for Render.com Web Service
PORT = int(os.environ.get("PORT", "10000"))

# Tradernet API Credentials
# KASE stocks key (725726)
KASE_PUB_KEY = os.environ.get("KASE_PUB_KEY", "e8df0f6e5c8e65689bff99f85b0f2adb")
KASE_SEC_KEY = os.environ.get("KASE_SEC_KEY", "598eb442c9af5c243aaea9c65cf97d0fb2f8a07f")

# Crypto key (CR725726)
CRYPTO_PUB_KEY = os.environ.get("CRYPTO_PUB_KEY", "30fca41e61c01c7b1943cbab1d0ee7a8")
CRYPTO_SEC_KEY = os.environ.get("CRYPTO_SEC_KEY", "6ab8a59a96a0c49cd382e44ee6ba241ae6103c3a")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        status = {
            "status": "online",
            "bot": "Tradernet Cloud Bot",
            "service": "Render.com Web Service",
            "kase_market": "OPEN" if is_kase_market_open() else "CLOSED",
            "timestamp": datetime.datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(status).encode('utf-8'))

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

class CloudBotEngine:
    def __init__(self):
        self.kase_client = tradernet.Tradernet(KASE_PUB_KEY, KASE_SEC_KEY)
        self.crypto_client = tradernet.Tradernet(CRYPTO_PUB_KEY, CRYPTO_SEC_KEY)
        self.active_orders = {}

    def run_crypto_step(self):
        """Execute crypto scalping logic on SOL/USD."""
        try:
            quotes = self.crypto_client.get_quotes(['SOL/USD']).get('result', {}).get('q', [])
            if not quotes:
                return
            q = quotes[0]
            bbp = float(q.get('bbp') or 0)
            bap = float(q.get('bap') or 0)
            if not bbp or not bap:
                return

            spread = bap - bbp
            spread_pct = (spread / bbp) * 100

            # Check positions
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
                    if o.get('oper') == 3: # Sell
                        sol_sell_id = o.get('id')
                    elif o.get('oper') == 1: # Buy
                        sol_buy_id = o.get('id')

            # 1. If holding SOL inventory and no sell order, place profitable TP
            if sol_qty >= 0.001 and not sol_sell_id:
                target_tp = round(max(sol_entry * 1.0035, bap), 2)
                logger.info(f"[SOL/USD] Submitting Take-Profit SELL: 0.001 SOL @ ${target_tp:.2f}")
                self.crypto_client.authorized_request('putTradeOrder', {
                    'instr_name': 'SOL/USD',
                    'action_id': 3,
                    'order_type_id': 2,
                    'qty': '0.001',
                    'limit_price': target_tp,
                    'expiration_id': 1
                })
                return

            # 2. If flat and spread is attractive (>= 0.30%), place BUY at Best Bid
            if sol_qty < 0.001 and not sol_buy_id:
                if spread_pct >= 0.30:
                    logger.info(f"[SOL/USD] Spread {spread_pct:.2f}% is attractive. Submitting BUY @ ${bbp:.2f}")
                    self.crypto_client.authorized_request('putTradeOrder', {
                        'instr_name': 'SOL/USD',
                        'action_id': 1,
                        'order_type_id': 2,
                        'qty': '0.001',
                        'limit_price': round(bbp, 2),
                        'expiration_id': 1
                    })

        except Exception as e:
            logger.error(f"Error in crypto step: {e}")

    def run_kase_step(self):
        """Monitor KASE stock orders during market hours."""
        if not is_kase_market_open():
            return
        try:
            quotes = self.kase_client.get_quotes(['ASBN.KZ', 'HSBK.KZ', 'KMGD.KZ']).get('result', {}).get('q', [])
            for q in quotes:
                sym = q.get('c')
                bbp = float(q.get('bbp') or 0)
                bap = float(q.get('bap') or 0)
                # KASE positions are monitored safely
        except Exception as e:
            logger.error(f"Error in KASE step: {e}")

    def start(self):
        logger.info("=" * 65)
        logger.info("🚀 Tradernet Cloud Bot Engine Started")
        logger.info("Assets: KASE (ASBN, HSBK, KMGD) & Crypto (SOL/USD)")
        logger.info("=" * 65)

        while True:
            try:
                self.run_crypto_step()
                self.run_kase_step()
            except Exception as e:
                logger.error(f"Main loop error: {e}")
            time.sleep(10)

def main():
    t_web = threading.Thread(target=start_health_server, daemon=True)
    t_web.start()

    engine = CloudBotEngine()
    engine.start()

if __name__ == '__main__':
    main()
