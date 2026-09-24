---
name: quant-history
description: >-
  Comprehensive guide and encyclopedia on the history of quantitative trading,
  famous market crashes, algorithmic strategies, and classical market microstructure theories.
  Use when analyzing market regimes, designing trading systems, evaluating flash crash mechanics,
  or researching classical quant methods (Jim Simons, Wyckoff, Kelly criterion, Trend Following).
---

# Quantitative Trading History & Market Microstructure Encyclopedia

## 1. Pillars of Quantitative Market Philosophy

### Jim Simons & Renaissance Technologies (Medallion Fund)
* **Core Philosophy**: Markets are not pure random walks. Short-term price fluctuations contain tiny, repeatable micro-anomalies caused by market microstructure, order execution latencies, and human behavioral biases.
* **Key Principles**:
  1. **High Volume of Independent Bets**: Rather than predicting multi-month macro moves, execute hundreds of statistically advantageous trades with a 50.7%–52.0% win rate or high risk-to-reward ratio.
  2. **Zero Emotional Discretion**: The algorithm must strictly follow its mathematical parameters without human panic intervention during drawdowns.
  3. **Non-Correlated Strategies**: Running market-making, mean-reversion, and momentum breakout engines simultaneously to generate steady Sharpe ratios (> 3.0).

### Richard Wyckoff & Market Cycles (1930s to Present)
* **Phase A (Selling Climax)**: Heavy panic dump driven by retail liquidations and stops hitting the book.
* **Phase B (Secondary Test & Absorption)**: Smart money passively absorbs resting sell liquidity.
* **Phase C (The Spring / Flash Wick)**: A sharp, brief breakdown beneath key support designed to trigger retail stop-losses. This is the **exact mechanic our Flash Sniper targets** — catching the spring wick before the rapid V-shape recovery.
* **Phase D (Markup)**: Trend continuation where the Rocket Rider takes over to ride momentum.

---

## 2. Anatomy of Historic Market Crashes & Flash Wicks

### 1. The 2010 Flash Crash (May 6, 2010)
* **What Happened**: The Dow Jones plunged ~9% (1,000 points) in minutes and recovered almost immediately.
* **Root Cause**: A massive automated algorithmic sell program met an evaporative void of passive liquidity (bids were pulled by HFT market makers).
* **Lesson for Bots**: When market depth evaporates, never place unbuffered market buys. Always use staggered Maker limit orders placed deep (-2.5% to -5.0%) with circuit breakers if systemic momentum (Lead-Lag) triggers.

### 2. March 12–13, 2020: The Crypto COVID Flash Crash
* **What Happened**: Bitcoin crashed from $8,000 to $3,800 (-52% in 24 hours), and Ether crashed to $88. BitMEX order books completely collapsed.
* **Root Cause**: Cascading margin liquidations. Liquidated long positions turned into market sell orders, eating every bid down to zero.
* **Lesson for Bots**: Liquidation cascades create asymmetric buying opportunities, but must be caught with exponential tiered sizing (Martingale/Geometric spacing like our STORM grid).

### 3. May 19, 2021: Altcoin Flash Liquidation
* **What Happened**: Top altcoins dropped 30–50% within 45 minutes, leaving massive wicks with immediate 25%+ rebounds within the same 4-hour candle.
* **Lesson for Bots**: Catching the bottom wick and deploying trailing take-profits (Rocket Rider) generates the highest risk-adjusted yield in crypto.

### 4. August 5, 2024: The Global Carry Trade Unwind
* **What Happened**: Nikkei plummeted 12%, Bitcoin dipped to $49,000 before surging back to $60,000 in 48 hours.
* **Lesson for Bots**: Macro volatility spikes trigger temporary systemic contagion. Our Lead-Lag sensor must detect BTC acceleration to temporarily freeze altcoin entry until the storm stabilizes.

---

## 3. Classical Algorithmic Strategies & Formulas

### Kelly Criterion for Position Sizing
Optimal fraction of capital to risk per trade:
$$f^* = \frac{p \cdot b - q}{b}$$
Where:
- $p$ = probability of a winning trade
- $q = 1 - p$ (probability of loss)
- $b$ = payoff ratio (average gain / average loss)

*Practical Rule*: In cryptocurrency markets with fat-tailed distributions, use **Quarter-Kelly ($f^* / 4$)** to avoid catastrophic drawdowns while compounding equity steadily.

### Mean Reversion (Ornstein-Uhlenbeck Process)
Price tends to oscillate around an equilibrium moving average or Volume-Weighted Average Price (VWAP):
$$dx_t = \theta (\mu - x_t) dt + \sigma dW_t$$
* $\theta$: speed of reversion to the mean
* $\mu$: long-term mean price (VWAP)
* $\sigma$: volatility amplitude

Our micro-grid uses this exact mechanic: taking advantage of the natural pull back to VWAP after localized momentum bursts.
