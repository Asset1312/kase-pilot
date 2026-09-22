import sys, os, datetime
from dotenv import load_dotenv
load_dotenv(r'C:\1\KASE-Pilot\.env')
sys.path.insert(0, r'C:\1\KASE-Pilot\deploy\tradernet-cloud-bot')
from bybit_client import BybitV5Client
client = BybitV5Client(api_key=os.getenv('BYBIT_API_KEY'), api_secret=os.getenv('BYBIT_API_SECRET'), domain='api.bybit.kz')
execs = client.get_execution_history('SUIUSDT', limit=40)
for e in execs:
    ts = datetime.datetime.fromtimestamp(int(e['execTime'])/1000, tz=datetime.timezone.utc) + datetime.timedelta(hours=5)
    side = e.get('side')
    p = e.get('execPrice')
    q = e.get('execQty')
    v = float(e.get('execValue', 0.0))
    fee = e.get('execFee')
    fee_c = e.get('feeCurrency')
    print(f"{ts.strftime('%Y-%m-%d %H:%M:%S')} | {side:<4} | Price: {p:>7} | Qty: {q:>6} | Val: ${v:>6.2f} | Fee: {fee} {fee_c}")
