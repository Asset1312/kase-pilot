"""Automated Real-Time Crypto News & Macro Sentiment Engine.

Fetches live public news feeds from CoinDesk, CoinTelegraph, and CryptoPanic,
computes real-time sentiment polarity scores, and caches results for
instant consumption by the Web Dashboard and Risk Dispatcher.
"""
import time
import json
import os
import urllib.request
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "live_news_feed.json")
CACHE_TTL_SECONDS = 600.0  # 10-minute cache

BULLISH_KEYWORDS = [
    "surge", "surges", "jump", "jumps", "rally", "rallies", "breakout", "ath",
    "record high", "bull", "bullish", "inflow", "inflows", "approval", "approved",
    "accumulate", "accumulation", "partnership", "gains", "gain", "soar", "soars",
    "upgrade", "launch", "adoption", "invest", "investment", "buy", "buying"
]

BEARISH_KEYWORDS = [
    "crash", "crashes", "plunge", "plunges", "dump", "dumps", "hack", "hacked",
    "exploit", "exploited", "lawsuit", "sec", "subpoena", "fraud", "scam",
    "bear", "bearish", "outflow", "outflows", "liquidation", "liquidated",
    "ban", "banned", "delist", "delisting", "insolvent", "insolvency", "drop",
    "drops", "slump", "slumps", "collapse", "decline", "warning", "panic"
]


def score_headline(text: str) -> Dict[str, Any]:
    """Computes a simple, robust keyword-weighted sentiment polarity score."""
    t_lower = text.lower()
    pos_hits = [w for w in BULLISH_KEYWORDS if w in t_lower]
    neg_hits = [w for w in BEARISH_KEYWORDS if w in t_lower]

    raw_score = len(pos_hits) - len(neg_hits)
    if raw_score > 0:
        sentiment = "BULLISH"
        color = "#10b981"
        badge = "🟢 Позитив"
    elif raw_score < 0:
        sentiment = "BEARISH"
        color = "#ef4444"
        badge = "🔴 Негатив"
    else:
        sentiment = "NEUTRAL"
        color = "#94a3b8"
        badge = "⚪ Нейтрально"

    return {
        "sentiment": sentiment,
        "score": raw_score,
        "badge": badge,
        "color": color,
    }


def fetch_rss_feed(url: str, source_name: str, max_items: int = 5) -> List[Dict[str, Any]]:
    """Fetches and parses an RSS feed using standard library only."""
    items: List[Dict[str, Any]] = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            # Standard RSS channel -> item
            for item in root.findall(".//item")[:max_items]:
                title_elem = item.find("title")
                link_elem = item.find("link")
                date_elem = item.find("pubDate")

                title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                date_str = date_elem.text.strip() if date_elem is not None and date_elem.text else ""

                if title:
                    s_info = score_headline(title)
                    items.append({
                        "title": title,
                        "link": link,
                        "source": source_name,
                        "date": date_str,
                        "sentiment": s_info["sentiment"],
                        "score": s_info["score"],
                        "badge": s_info["badge"],
                        "color": s_info["color"],
                    })
    except Exception:
        pass
    return items


def get_latest_market_news(force_refresh: bool = False, max_items: int = 8) -> List[Dict[str, Any]]:
    """Returns curated live crypto news with sentiment, using a local TTL cache."""
    now = time.time()
    if not force_refresh and os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
                if now - cached.get("cached_at", 0) < CACHE_TTL_SECONDS:
                    return cached.get("news", [])[:max_items]
        except Exception:
            pass

    # Aggregating multiple top reputable sources
    all_news: List[Dict[str, Any]] = []
    feeds = [
        ("https://cointelegraph.com/rss", "CoinTelegraph"),
        ("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"),
    ]

    for feed_url, s_name in feeds:
        all_news.extend(fetch_rss_feed(feed_url, s_name, max_items=4))

    # If feeds succeed, cache them
    if all_news:
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"cached_at": now, "news": all_news}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return all_news[:max_items]


if __name__ == "__main__":
    news = get_latest_market_news(force_refresh=True)
    print(f"Fetched {len(news)} live headlines:")
    for n in news:
        print(f"[{n['source']}] {n['badge']}: {n['title']}")
