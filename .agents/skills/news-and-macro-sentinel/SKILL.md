---
name: news-and-macro-sentinel
description: >-
  Systematic intelligence guide for monitoring crypto news, macroeconomic events,
  Fed interest rate decisions, CPI inflation releases, and institutional capital flows (ETFs).
  Use when analyzing market sentiment, reacting to breaking news, or scheduling event-driven risk mitigation.
---

# News and Macroeconomic Sentinel Guide

## 1. High-Impact Macroeconomic Calendar

When high-volatility macroeconomic data is released, cryptocurrency spreads widen significantly and volatility explodes. The agent monitors the following recurring events:

| Event | Frequency | Typical Impact Window | Bot Action |
| :--- | :--- | :--- | :--- |
| **US CPI (Consumer Price Index)** | Monthly (usually 2nd week) | 15 min before to 60 min after | Switch to STORM regime (wider spacing) |
| **FOMC / Powell Press Conference** | Every 6 weeks (Wednesdays 00:00 Astana) | During conference (1-2 hours) | Enable DCA protection, widen sniper trap |
| **US Non-Farm Payrolls (NFP)** | 1st Friday of month (18:30 Astana) | 30 minutes | Widen Step 1 discounts |
| **Quarterly Crypto Options Expiry (Deribit)** | Last Friday of March/June/Sept/Dec | 13:00–16:00 Astana | Expect high gamma pinning |

---

## 2. Crypto-Native Sentiment Drivers

### 1. Spot ETF Net Inflows / Outflows
* Daily reports from Farside Investors / CoinGlass on US Spot Bitcoin & Ethereum ETFs.
* **Bullish Signal**: Sustained net inflows > $200M/day for 3+ consecutive days (triggers expansion to Trio mode).
* **Bearish Signal**: Sustained net outflows > $150M/day (tighten risk limits, keep $10 reserve).

### 2. Major Token Unlocks (Vesting Cliff Events)
* Large unlocks (> 3% of circulating supply within 24h) typically cause front-running sell pressure 1–3 days prior, followed by an oversold bounce.

### 3. Regulatory Announcements & SEC Actions
* News of lawsuits, exchange enforcement actions, or geopolitical tensions create sudden asymmetric spikes. The Flash Sniper is ideally tuned to catch the bottom wick of these sudden FUD-driven drops.

---

## 3. Automated News Sentiment Scoring Framework

When parsing headlines, the sentiment engine computes a score from -1.0 (Extreme Fear / Bearish) to +1.0 (Extreme Greed / Bullish):

* **High Positive Keywords (+0.5 to +1.0)**:
  `approval`, `etf inflow`, `partnership`, `breakout`, `record high`, `institutional accumulation`, `upgrade`, `mainnet launch`
* **High Negative Keywords (-0.5 to -1.0)**:
  `hack`, `exploit`, `sec lawsuit`, `investigation`, `insolvent`, `outflow`, `liquidation cascade`, `ban`, `delisting`
* **Neutral / Factual (0.0)**:
  `consolidation`, `trading volume`, `rebalance`, `options expiry`

If aggregated 1-hour sentiment drops below -0.60, the bot automatically enforces the **STORM Deep Defense** spacing.
