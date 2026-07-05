# Insight Round 4 — Fixing the Foundation

> **Context**: Round 3 confirmed our simulation is **systematically optimistic**. Real EV is likely worse than -0.21%. Our position sizing is 2× full-Kelly even at 8x leverage. The foundation must be fixed BEFORE any parameter changes matter. This round focuses on **exact implementation specs** for the 3 critical simulation fixes and **sizing at $10**.

---

## Order of Operations Question

**S1.** Claude's checklist says: fix simulation (slippage, SL exit, correlation) THEN replay THEN switch params. But fixing simulation changes all historical metrics.

**If we fix the simulation model and re-run paper trading, we lose comparability with our ~200 existing trades (those were measured under optimistic assumptions). Should we:**
- (a) Fix sim → start fresh paper trading from zero → wait for new data
- (b) Fix sim → replay historical entries with NEW cost model applied on top → get adjusted metrics immediately
- (c) Fix sim → both: replay historical + start fresh forward

**Which approach gives us actionable data fastest without sacrificing trust?**

---

## Slippage Fix — Exact Implementation

**S2.** Claude proposed mixture distribution:
- 80% of time: Gaussian(μ=3, σ=2) cap 8bps (normal conditions)
- 20% of time: Gaussian(μ=20, σ=10) cap 60bps (volatile conditions)

**How do we determine WHICH regime we're in at entry time? Options:**
- (a) Random 20% of trades → simple but detached from reality
- (b) Tie to volume_ratio: if vol_ratio > 5x, use fat-tail regime
- (c) Tie to ATR%: if ATR% > threshold, use fat-tail regime
- (d) Tie to kline volatility: if candle range > 2× average range, use fat-tail

**Which trigger is most correlated with actual adverse slippage on meme coins?**

**S3.** The 20% probability for fat-tail regime — is this a fixed prior, or should it scale? On a day when BTC dumps 5%, maybe 50%+ of meme coin entries hit volatile conditions, not 20%.

**Should the mixture weight be dynamic (function of market regime)? If yes, what's the simplest regime indicator?**

**S4.** For SL exits specifically: Claude said slippage should be **1.5× worse** than normal market orders due to adverse selection (SL triggers BECAUSE price is moving against us).

**Concrete proposal: SL exit slippage = entry slippage × 1.5, using the SAME mixture distribution. So:**
- Normal regime SL exit: Gaussian(μ=4.5, σ=3) cap 12bps
- Volatile regime SL exit: Gaussian(μ=30, σ=15) cap 90bps

**Is 1.5× the right multiplier, or is there empirical data suggesting a different ratio?**

---

## Position Sizing at $10 — The $5 Minimum Problem

**S5.** Claude's Kelly calculation with correlated positions: target `N×e×L ≤ 2.0` (half-Kelly).

Options at L=8:
- N=3, e=8.5% → notional = $10 × 0.085 × 8 = $6.80 per position (above $5 min ✓)
- N=2, e=13% → notional = $10 × 0.13 × 8 = $10.40 per position (above $5 min ✓)
- N=1, e=25% → notional = $10 × 0.25 × 8 = $20 per position (comfortable ✓)

**At $10 bankroll with $5 Binance minimum, N=3 e=8.5% gives us $6.80 notional per trade — barely above minimum. If any partial fill occurs (8% chance), we could drop below $5 notional. Is N=2 e=13% more practical, or is N=1 e=25% the only safe option?**

**S6.** With N=2 or N=1, our trade throughput drops dramatically. At N=1, we can only hold ONE position at a time. If TP=3% takes 30+ minutes to hit, we might only do 2-3 trades per hour.

**At N=1, L=8, e=25%, TP=3%, SL=2%, WR=45%: expected profit per trade = 0.05% of notional = $0.01. At 3 trades/hour = $0.03/hour. Is this even worth running, or should we focus on validation-only (prove the edge exists) rather than profit?**

**S7.** Alternative: what if we use L=3 (more conservative) and keep N=3, e=20%?
- Notional per position = $10 × 0.20 × 3 = $6 (above $5 min ✓)
- N×e×L = 3 × 0.20 × 3 = 1.8 (half-Kelly ✓)
- SL 2% loss = 6% of margin = 3.6% of bankroll per position
- 3 positions all hitting SL = 10.8% of bankroll (survivable ✓)

**Is L=3 more appropriate for $10 bankroll? What's the minimum leverage needed to make TP 3% worth capturing on $6 notional?**

---

## Binance OCO / Conditional Orders

**S8.** Claude mentioned native OCO-style pairing for STOP_MARKET + TAKE_PROFIT_MARKET. 

**Does Binance USDM Futures actually support OCO orders? Our understanding:**
- Spot Binance has OCO (limit + stop-limit pair)
- USDM Futures has `STOP_MARKET` and `TAKE_PROFIT_MARKET` as separate order types
- But no native OCO that auto-cancels the other leg

**If no native OCO: we need to manually cancel the SL order when TP hits (and vice versa). In our 2s polling loop, there's a ~1-2s window where both orders could be active. Is this a real risk, or is Binance's order matching atomic enough that we won't get double-filled?**

**S9.** When we place a stop-market order on Binance USDM:
- `workingType: MARK_PRICE` — triggers on mark price, not last price
- `closePosition: true` — closes entire position when triggered
- `stopPrice: <trigger_level>` — calculated from entry price and SL%

**Is mark price the right choice for meme coins, or does it lag too much? Mark price is a weighted average that might be less volatile than last price — could it fail to trigger during a flash crash where last price crashes but mark price stays higher?**

---

## Replay Pipeline — One Clarification

**S10.** Claude said use 1m klines and max_hold_time as the window. Our max_hold is currently 900s (15 min).

**In the replay, when we iterate 1m candles: if candle N has both high > TP AND low < SL, which one "happened first"?** Since we can't see intra-candle order of events:
- Conservative approach: assume SL hit first (worst case for longs)
- Or: use the open price direction to guess (if open < entry, SL likely hit first)
- Or: skip the ambiguous candle and don't count the trade

**What's the standard practice for handling this ambiguity in backtesting?**

---

## The Meta Question

**S11.** We've now done 4 rounds of analysis. The core finding is consistent: **our simulation is too optimistic, our sizing is too aggressive, and our edge might not exist.**

Given that:
- Real EV is likely < -0.21%
- Simulation needs 3 major fixes before we can trust any number
- $10 bankroll can't generate meaningful profit even with correct parameters
- The bot is paper-trading only, not live

**Should we pivot the entire effort from "optimize the bot" to "build a trustworthy measurement system first"?** Meaning: stop trying to find profitable parameters, and instead focus 100% on making the simulation accurate enough that we can actually MEASURE whether any edge exists. Once the measurement tool is trustworthy, THEN find the edge.

**Or is there a faster path — like running a small live test ($2-3) on testnet to get ground-truth cost data, then calibrate our simulation from that?**

---

## Updated Data Summary

| Metric | Previous Value | Updated Value (after R3 analysis) |
|--------|---------------|----------------------------------|
| EV per trade | -0.21% | **Likely more negative** (optimistic sim) |
| Simulation trust | "Borderline" | **Not trustworthy** for live decisions |
| Kelly sizing | N=5, e=20%, L=8 (8.0× bankroll) | **2× full-Kelly, 4× half-Kelly** — way too aggressive |
| Correct half-Kelly target | N/A | N×e×L ≤ 2.0 (e.g., N=3 e=8.5% L=8) |
| Slippage model | Gaussian cap 5bps | **Needs mixture distribution** (80/20 split) |
| SL exit slippage | Zero (stop-limit assumption) | **1.5× worse than market** (adverse selection) |
| Position correlation | Independent | **Correlated** — Kelly must treat as one joint bet |
