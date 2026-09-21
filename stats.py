import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import datetime
from collections import defaultdict
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from bybit_standalone_bot import BybitV5Client, BYBIT_API_KEY, BYBIT_API_SECRET

client = BybitV5Client(BYBIT_API_KEY, BYBIT_API_SECRET, domain='api.bybit.kz')
execs = client.get_execution_history('SUIUSDT', limit=100)

hourly_stats = defaultdict(lambda: {'count': 0, 'volume_usdt': 0.0, 'buys': 0, 'sells': 0})
dow_stats = defaultdict(lambda: {'count': 0, 'volume_usdt': 0.0})
days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

for e in execs:
    t = datetime.datetime.fromtimestamp(int(e['execTime'])/1000, tz=datetime.timezone.utc) + datetime.timedelta(hours=5)
    val = float(e.get('execValue', 0.0))
    side = e.get('side')
    
    h = t.hour
    hourly_stats[h]['count'] += 1
    hourly_stats[h]['volume_usdt'] += val
    if side == 'Buy':
        hourly_stats[h]['buys'] += 1
    else:
        hourly_stats[h]['sells'] += 1
        
    dow = days[t.weekday()]
    dow_stats[dow]['count'] += 1
    dow_stats[dow]['volume_usdt'] += val

print('=== РАСПРЕДЕЛЕНИЕ ПО ЧАСАМ (ВРЕМЯ АСТАНЫ, UTC+5) ===')
for h in sorted(hourly_stats.keys()):
    st = hourly_stats[h]
    print(f"{h:02d}:00 - {h:02d}:59 | Сделок: {st['count']:2d} (Куп: {st['buys']:2d}, Прод: {st['sells']:2d}) | Оборот: ${st['volume_usdt']:>7.2f}")

print('\n=== РАСПРЕДЕЛЕНИЕ ПО ДНЯМ НЕДЕЛИ ===')
for d in days:
    if d in dow_stats:
        st = dow_stats[d]
        print(f"{d}: Сделок: {st['count']:2d} | Оборот: ${st['volume_usdt']:>7.2f}")
