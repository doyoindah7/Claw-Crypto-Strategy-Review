# Insight Follow-Up — Round 2

> **Context**: This is a follow-up to `insight.md`. An AI reviewer (Claude) confirmed the core structural problem: **TP/SL too tight relative to transaction cost**. This round digs deeper into *implementation specifics* and *quantitative thresholds* that the first round identified but didn't resolve.

---

## Cost-to-Target Structure (Q3/Q4 deep dive)

**F1.** You confirmed: widen TP/SL relative to cost. Our constraint: $10 bankroll, 20x leverage, max 5 concurrent positions.

If we shift to TP 3% / SL 2% (Fifteen-inspired):
- Position size: 20% equity × 20x = $40 notional → SL 2% = $0.80 loss (8% of bankroll)
- With 5 concurrent positions all hitting SL: -40% bankroll in one cycle

**What's the maximum SL% we can run on $10 without risking ruin? Give the math for max concurrent position worst-case.**

**F2.** At TP 3% / SL 2%, round-trip cost 0.178% becomes only 5.9% of TP (vs 17.8% at TP 1%). Breakeven WR drops to ~40%.

But our observed WR of 35-45% was measured at TP 1%/SL 0.5%. **Does widening stops change the win rate? If WR drops from 40% → 30% when we widen TP from 1% → 3%, does the lower breakeven still save us? What's the WR-vs-TP elasticity you'd estimate?**

**F3.** Fifteen ran TP 8%/SL 7.6% with NO leverage. If we replicate that on Binance:
- $10 × 20% = $2 per trade, no leverage → TP 8% = $0.16 profit, SL 7.6% = $0.152 loss
- But we'd need 8%+ moves on meme coins, which happen but take hours

**Is an 8% TP realistic for intraday meme scalp on Binance? What's the average time-to-8% for top-30 meme perpetuals?**

---

## Confidence Formula Fix (Q2 deep dive)

**F4.** Current formula: `0.55 + min(0.15, vol_ratio/20) + min(0.15, |momentum|/5)`. Problem: additive, one weak component passes.

Proposed fix: **multiplicative** — `base × vol_factor × mom_factor`, where both must be > 1.0 to exceed threshold.

**Design a concrete replacement formula where BOTH vol_ratio AND momentum must meaningfully contribute. Show that a 2.0x vol + 0.08% momentum FAILS, while 4.0x vol + 0.5% momentum PASSES.**

**F5.** We don't have per-confidence-bucket win rate data (no raw trade logs on this system). But we know aggregate WR is 35-45% and the threshold is 0.54.

**If we raise threshold to 0.65 and lose 40% of signals, but the remaining signals have WR >50%, is that a net positive? What's the minimum WR improvement needed to offset the volume loss?**

---

## ATR-Normalized Momentum (Q9 deep dive)

**F6.** You suggested ATR normalization instead of fixed 0.08% threshold. Current implementation:
- Momentum = ROC% over 3 candles on 5m klines
- Threshold = 0.08% (fixed)

Proposed: `momentum_threshold = k × ATR%`, where k is a scaling factor.

**What k value makes sense? If ATR% on a meme coin is typically 2-5%, then k=0.04 gives threshold 0.08-0.20%. Is that the right range? What does k=0.04 imply for low-vol majors (ATR% 0.5%) — threshold 0.02%, which is even more noise-sensitive?**

**F7.** You also suggested "persist 2-3 candle" test. Current logic: momentum measured on single 3-candle window.

**Define "persist": does momentum need to be positive on 2 out of 3 consecutive evaluation windows? Or does the ROC need to be above threshold for 2 consecutive candles? How does this interact with the first-match-wins tier system?**

---

## ADX Threshold (Q10 deep dive)

**F8.** We can't backtest (paper trading only, no historical data pipeline). Minimum viable A/B test: run ADX 15 and ADX 20 on alternate signals, compare.

**How many trades per group for statistical significance at p<0.05? If WR at ADX 15 is 38% and WR at ADX 20 is 45%, how many trades confirm this isn't variance? Give the sample size formula.**

---

## Execution Architecture (Q5 deep dive)

**F9.** You said WebSocket + stop-market on exchange is prerequisite. Our bot runs on a $5 VPS, Python synchronous, REST polling every 2s.

**Minimum viable fix WITHOUT WebSocket**: instead of 2s polling, check if SL would have been hit using the kline high/low since last check (not just current price). This uses existing REST data. **Does this approach close the SL overshoot gap? What's the worst-case overshoot with 5m kline high/low checking vs tick-by-tick WebSocket?**

**F10.** Binance stop-market orders: we don't use them because we simulate everything in paper mode. If we switch to live:

**Does Binance USDM support stop-market orders that trigger on mark price (not last price)? If yes, this eliminates polling SL entirely — the exchange handles it. What's the fee difference between stop-limit and stop-market?**

---

## Leverage Optimization (Q7/Q8 deep dive)

**F11.** You confirmed leverage doesn't create edge. But at $10 bankroll, no leverage means $2 position → TP 3% = $0.06 profit per trade. That's $0.06 × 10 trades/day × 40% WR = $0.24/day.

**At what bankroll level does zero-leverage Fifteen-style become viable? Give the minimum bankroll for $1/day expected profit at TP 3%/SL 2%/WR 45%.**

**F12.** If we must use leverage for capital efficiency: **is there an optimal leverage given fee structure?** Fee = 0.05% × leverage × notional. Net edge per trade = (WR × TP - (1-WR) × SL) - fee_round_trip. **Plot or calculate: for WR 40%, TP 3%, SL 2%, what leverage maximizes expected daily PnL?**

---

## Concrete Parameter Proposal

**F13.** Given everything above, **give us ONE concrete parameter set** to test next:

| Parameter | Current | Proposed |
|-----------|---------|----------|
| TP | 1.0% | ? |
| SL | 0.5% | ? |
| Leverage | 20x | ? |
| Position size | 20% equity | ? |
| Confidence threshold | 0.54 | ? |
| ADX | 15 | ? |
| Momentum threshold | 0.08% | ? |
| Max positions | 5 | ? |

**With expected breakeven WR and estimated actual WR based on your analysis.**

---

## Data Available for Further Analysis

We don't have raw trade logs on this system. What we DO have (see `data/PERFORMANCE_METRICS.md`):
- Aggregate performance: WR 35-45%, avg win +0.7-1.2%, avg loss -0.5-0.8%
- Cost breakdown: round-trip 17.75-25.5 bps on meme coins
- SL overshoot: 0.72-1.60% observed vs 0.5% configured
- Signal tier distribution: Tier 1 ~40%, Tier 4 ~20%, Tier 5 ~15%
- Fifteen reference: TP 8%, SL 7.6%, 0.002% momentum, no leverage, WR ~40%

**If you need specific data points not covered here, ask. We can extract from the live bot's SQLite database.**
