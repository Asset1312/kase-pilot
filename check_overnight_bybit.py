import sys, json, os, datetime, dotenv
sys.path.insert(0, 'deploy/tradernet-cloud-bot')
from bybit_client import BybitV5Client
dotenv.load_dotenv()
c = BybitV5Client(os.getenv('BYBIT_API_KEY'), os.getenv('BYBIT_API_SECRET'))
b = c.get_wallet_balance()

print(f"Total USD: {b.get('total_usd')}")
print(f"Available USDT: {b.get('available_usdt')}")
print(f"Locked USDT: {b.get('locked_usdt')}")
print(f"Coins: {b.get('coins')}")

execs = c.get_execution_history('SUIUSDT', limit=50)
print(f"\nTotal Executions found: {len(execs)}")
sells = [e for e in execs if e.get('side') == 'Sell']
buys = [e for e in execs if e.get('side') == 'Buy']
print(f"Sells (Take-Profits hit): {len(sells)}")
print(f"Buys filled: {len(buys)}")

print("\n--- CHRONOLOGICAL TRADE LOG ---")
all_trades = sorted(execs, key=lambda x: float(x.get('execTime', 0)))
for t in all_trades:
    t_str = datetime.datetime.fromtimestamp(float(t['execTime'])/1000).strftime('%Y-%m-%d %H:%M:%S')
    side = t.get('side')
    p = t.get('execPrice')
    q = t.get('execQty')
    v = t.get('execValue')
    fee = t.get('execFee')
    curr = t.get('feeCurrency')
    print(f"[{t_str}] {side:<4} {q:>6} SUI @ ${p} = ${v:>6} USDT (Fee: {fee} {curr})")
