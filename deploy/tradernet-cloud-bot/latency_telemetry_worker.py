import asyncio
import json
import time
import logging
from collections import deque
import websockets

logger = logging.getLogger("LatencyTelemetry")

class LatencyBenchmarkEngine:
    def __init__(self, symbol_bybit="SUIUSDT", threshold_pct=0.25, ws_url="wss://stream.bybit.kz/v5/public/spot"):
        self.symbol_bybit = symbol_bybit
        self.threshold_pct = threshold_pct
        self.ws_url = ws_url
        
        # Состояние мирового рынка
        self.last_bybit_mid = None
        self.pending_impulses = deque(maxlen=20)  # Очередь неразрешенных импульсов
        
        # Статистика задержек (мс)
        self.delta_records = deque(maxlen=500)
        self.negative_count = 0  # Снятия быстрее нашего RTT (<250ms)
        self.positive_count = 0  # Окна доступной ликвидности (>=250ms)

    def register_tradernet_quote(self, bid: float, ask: float, timestamp_ms: float = None):
        """Вызывается при получении каждого нового тика/котировки от Tradernet."""
        if bid <= 0 or ask <= 0 or ask <= bid:
            return
        now_ms = timestamp_ms or (time.time() * 1000.0)
        tn_mid = (bid + ask) / 2.0

        # Сверяем со списком недавних импульсов Bybit
        resolved = []
        for impulse in list(self.pending_impulses):
            # Проверяем, сдвинулся ли стакан Tradernet в сторону импульса
            price_diff_pct = abs(tn_mid - impulse["tn_mid_start"]) / impulse["tn_mid_start"] * 100.0
            
            if price_diff_pct >= 0.15:  # Маркет-мейкер отреагировал на движение
                delta_t = now_ms - impulse["t0_ms"]
                self.delta_records.append(delta_t)
                
                if delta_t < 250:
                    self.negative_count += 1
                else:
                    self.positive_count += 1
                    
                logger.info(
                    f"⚡ [DELTA-T DETECTED] Dir: {impulse['direction']} | "
                    f"Bybit impulse: {impulse['bybit_pct']:.2f}% | "
                    f"Tradernet delay: {delta_t:.1f} ms"
                )
                resolved.append(impulse)

        for item in resolved:
            try:
                self.pending_impulses.remove(item)
            except ValueError:
                pass

    async def run_bybit_stream(self, get_tradernet_mid_func):
        """Подключение к публичному WebSocket Bybit v5."""
        url = self.ws_url
        subscribe_payload = {
            "op": "subscribe",
            "args": [f"tickers.{self.symbol_bybit}"]
        }

        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    await ws.send(json.dumps(subscribe_payload))
                    logger.info(f"✅ Bybit WebSocket подключен: {self.symbol_bybit}")

                    async for msg in ws:
                        data = json.loads(msg)
                        topic = data.get("topic", "")
                        
                        if "tickers" in topic:
                            tick_data = data.get("data", {})
                            last_price = float(tick_data.get("lastPrice", 0.0) or 0.0)
                            if last_price <= 0:
                                continue

                            now_ms = time.time() * 1000.0

                            if self.last_bybit_mid is not None and self.last_bybit_mid > 0:
                                pct_change = (last_price - self.last_bybit_mid) / self.last_bybit_mid * 100.0

                                # Фиксация импульса выше порогового значения
                                if abs(pct_change) >= self.threshold_pct:
                                    current_tn_mid = get_tradernet_mid_func()
                                    if current_tn_mid > 0:
                                        self.pending_impulses.append({
                                            "t0_ms": now_ms,
                                            "bybit_price": last_price,
                                            "bybit_pct": pct_change,
                                            "direction": "UP" if pct_change > 0 else "DOWN",
                                            "tn_mid_start": current_tn_mid
                                        })
                                        logger.info(f"🎯 Импульс Bybit {pct_change:+.2f}% зафиксирован в {now_ms:.0f} ms")

                            self.last_bybit_mid = last_price

            except Exception as e:
                logger.error(f"❌ Bybit WS ошибка: {e}. Переподключение через 3с...")
                await asyncio.sleep(3)

    def get_latency_report(self) -> dict:
        """Формирует срез перцентилей для JSON-эндпоинта."""
        if not self.delta_records:
            return {
                "samples_count": 0,
                "status": "COLLECTING_DATA",
                "endpoint": self.ws_url,
                "latest_bybit_price": self.last_bybit_mid,
                "median_ms": None,
                "p90_ms": None,
                "p95_ms": None,
                "toxic_cancellations_pct": 0.0,
                "tradable_windows_pct": 0.0
            }

        sorted_d = sorted(self.delta_records)
        n = len(sorted_d)
        p50 = sorted_d[int(n * 0.50)]
        p90 = sorted_d[int(n * 0.90)]
        p95 = sorted_d[min(int(n * 0.95), n - 1)]

        return {
            "samples_count": n,
            "status": "ACTIVE",
            "endpoint": self.ws_url,
            "latest_bybit_price": self.last_bybit_mid,
            "median_ms": round(p50, 1),
            "p90_ms": round(p90, 1),
            "p95_ms": round(p95, 1),
            "toxic_cancellations_pct": round((self.negative_count / n) * 100.0, 1),
            "tradable_windows_pct": round((self.positive_count / n) * 100.0, 1)
        }
