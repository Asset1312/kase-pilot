import os
import sys
import dotenv
import datetime

dotenv.load_dotenv()
sys.path.insert(0, "deploy/tradernet-cloud-bot")
from bybit_client import BybitV5Client

c = BybitV5Client(os.getenv("BYBIT_API_KEY"), os.getenv("BYBIT_API_SECRET"))
execs = c.get_execution_history("SUIUSDT", limit=100)

# Friday 18.09 17:00 UTC+5 is approx 1789732800000 ms
friday_ts = 1789732800000
weekend_execs = [e for e in execs if float(e["execTime"]) >= friday_ts]
weekend_sells = [e for e in weekend_execs if e["side"] == "Sell"]
weekend_buys = [e for e in weekend_execs if e["side"] == "Buy"]

total_sell_val = sum(float(s["execPrice"]) * float(s["execQty"]) for s in weekend_sells)
fees = sum(float(e["execFee"]) for e in weekend_execs)

w = c.get_wallet_balance()
usdt = w["coins"]["USDT"]["balance"]
sui = w["coins"]["SUI"]["balance"]
mnt = w["coins"]["MNT"]["balance"]

ticker_res = c._request("GET", "/v5/market/tickers", params={"category": "spot", "symbol": "SUIUSDT"})
sui_price = float(ticker_res["result"]["list"][0]["lastPrice"])
mnt_price = 0.78
total_equity = usdt + (sui * sui_price) + (mnt * mnt_price)

print(f"--- WEEKEND STATS (18.09 17:00 - 21.09 07:50) ---")
print(f"Closed Cycles (Sells): {len(weekend_sells)}")
print(f"Executed Buys: {len(weekend_buys)}")
print(f"Total Turnover Sold: ${total_sell_val:.2f} USDT")
print(f"Current SUI Price: ${sui_price:.4f} (Rallied from $0.7840 to ${sui_price:.4f}!)")
print(f"USDT Balance: ${usdt:.2f} (Free: ${w['coins']['USDT']['free']:.2f}, In Orders: ${w['coins']['USDT']['locked']:.2f})")
print(f"SUI Balance: {sui:.4f} SUI (${sui * sui_price:.2f})")
print(f"MNT Fuel: {mnt:.4f} MNT (${mnt * mnt_price:.2f})")
print(f"TOTAL EQUITY: ${total_equity:.2f} USDT")

print("\n--- ALL WEEKEND SELL ORDERS (CYCLES) ---")
for s in reversed(weekend_sells):
    dt = datetime.datetime.fromtimestamp(float(s["execTime"])/1000).strftime("%d.%m %H:%M:%S")
    q = s["execQty"]
    p = s["execPrice"]
    v = float(s["execPrice"]) * float(s["execQty"])
    print(f"[{dt}] Sold {q} SUI @ ${p} -> ${v:.2f}")
