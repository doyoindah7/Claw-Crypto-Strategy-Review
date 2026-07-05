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

## Side Quest: Alternative Strategy Research

> We've spent 4 rounds diagnosing why our meme-coin scalping strategy has negative EV. The diagnosis is clear. Now we need to know: **is there a better strategy we should be running instead?** These questions ask Claude to research and propose alternative strategies — any timeframe (HFT scalping, intraday, swing hourly/daily) is acceptable as long as the edge after realistic costs is substantially better than our current scalping approach.

---

### S12. HFT Scalping on Binance USDM — Is It Viable for Us?

We currently use 2s REST polling. True HFT scalping (sub-second) requires WebSocket + co-location + memory of order book state. Our infrastructure: $5 VPS, Python synchronous, no WebSocket.

**Is there ANY form of high-frequency scalping on Binance USDM Futures that produces positive EV after realistic costs with our infrastructure constraints?** Specifically:

- **Micro-scalping majors**: TP 0.3-0.5%, SL 0.2-0.3%, on BTC/ETH where spread is 5bps. At 0.3% TP, cost/TP = 0.178%/0.3% = 59% — even worse than our meme approach. Is this viable ONLY with maker fees (0.02%) and limit orders?
- **Tick-scalping with order book imbalance**: Read L2 depth, detect buy/sell wall asymmetry, enter on the strong side for 1-3 tick moves. Requires WebSocket + order book data. **What's the estimated EV per trade for this approach after 5bps taker fees? Is the edge large enough to justify the infrastructure upgrade?**
- **Funding rate micro-scalping**: Enter a position seconds before funding settlement, capture the payment, exit immediately after. **Is this a real edge, or does the market already price funding into the mark price? What's the typical slippage cost of entering+exiting around settlement time?**

**For each approach: estimate the EV per trade, required infrastructure, and minimum viable bankroll. If none are viable at $10, state the minimum capital needed.**

---

### S13. Swing Trading — Hourly/Daily Timeframe

Our current strategy holds positions for 0-15 minutes. What if we dramatically increase the holding period?

**Research and propose a concrete swing trading strategy for Binance USDM Futures that:**
- Holds positions for 4 hours to 3 days
- Targets TP of 5-15% (not 1-3%)
- Works on $10 bankroll with L=2-5
- Has a documented or theoretically justified edge after realistic execution costs

**Specific questions:**
- **What signal generates the edge?** EMA crossover? Mean-reversion at Bollinger bands? Breakout with volume? Funding rate extreme + patience? On-chain flow? Give us the logic, not just the indicator name.
- **What's the estimated WR at TP 8%/SL 6% on crypto perpetuals?** Is there empirical data or academic research on momentum/mean-reversion strategies at this timeframe?
- **Cost structure**: at TP 8% on majors (5bps spread), cost/TP = 0.10%/8% = 1.25%. That's better than Fifteen's 3.1%. **Is swing trading on majors structurally cheaper than scalping on memes?**
- **How many trades per week?** If a swing strategy generates 2-5 signals per week at 45% WR and 1.5:1 R:R, that's 2-5 × (0.45×8% - 0.55×6%) = 2-5 × 0.3% = 0.6-1.5% per week of notional. At $10 × 20% × 3x = $6 notional, that's $0.018-$0.045 per week. **Is this math roughly right, or are we missing something?**

---

### S14. The Fifteen-to-Crypto Direct Translation

Paper Fifteen on Polymarket was profitable: EMA+ROC, TP 8%, SL 7.6%, no leverage, ~40% WR. We've been trying to adapt this to crypto but changed everything (8 tiers, tight stops, leverage).

**What if we did a DIRECT translation of Fifteen to Binance USDM?** Meaning:
- Same signal: EMA(9) crossover + ROC(3) on 5m klines
- Same stops: TP 8%, SL 7.6% (or proportional: TP 5%, SL 4.5%)
- Same sizing: no leverage, 20% equity per trade
- Target: majors only (BTC/ETH/SOL) where spread = 5bps
- Entry: market order (taker)

**Calculate the expected EV:**
- Entry cost: half-spread + slippage + fee = 2.5bps + 3bps + 5bps = 10.5bps per side
- Exit cost (SL/TP): fee only = 5bps (assuming stop-market on exchange)
- Total round-trip: ~16bps = 0.16%
- At TP 8%: cost/TP = 0.16%/8% = 2.0% (better than Fifteen's 3.1% on Polymarket!)
- At TP 5%: cost/TP = 0.16%/5% = 3.2% (roughly equal to Fifteen)

**Is this viable? What WR can we expect for EMA+ROC momentum on 5m BTC klines with TP 5-8%?** If WR is ≥35% at TP 8%/SL 7.6%, the strategy is profitable (breakeven = 49.3% at 1:1 R:R... wait, that's NOT profitable). **Recalculate**: at TP 8%, SL 7.6%, cost 0.16%: breakeven WR = (7.6+0.16)/(8+7.6+0.16) = 7.76/15.76 = 49.2%. That's HIGH. We need 49%+ WR for a strategy that Fifteen runs at ~40% WR.

**This suggests Fifteen's exact parameters DON'T work on Binance even with tight spreads. The cost is similar but the R:R is 1:1, so breakeven is ~49%. We need either higher WR or better R:R. What R:R would make a Fifteen-style approach viable at 40% WR?** (Answer: R:R > 1.5:1 → TP 8%/SL 5% or TP 5%/SL 3%).

---

### S15. Known Profitable Crypto Bot Strategies — Literature Review

**We need honesty here.** We've spent 4 rounds analyzing a strategy that has negative EV. Before we invest more time in fixing the measurement system, we need to know:

**Is there ANY publicly documented, live-traded, audited crypto bot strategy on Binance USDM Futures that has demonstrated positive EV after all costs over 1000+ trades?** We don't mean backtests. We don't mean theoretical frameworks. We mean:
- A bot that actually ran on Binance with real money
- Trackable trade history (verified PnL)
- 1000+ trades over 30+ days
- Net positive after all fees, spread, and slippage

**If yes: what strategy class does it belong to? (market-making, momentum, mean-reversion, arbitrage, funding capture, other?) What was the approximate EV per trade? What infrastructure was required?**

**If no such publicly documented strategy exists: tell us that. It's better to know the landscape is barren than to keep searching for something that may not exist at our scale.**

---

### S16. Strategy Comparison Framework

Given everything you know about our constraints (Binance USDM, $10 bankroll, Python on $5 VPS, 2s polling), **rank ALL plausible strategy classes by expected EV per trade after realistic costs, from highest to lowest.** For each, provide:

| Strategy Class | Timeframe | TP/SL | Est. WR | Est. EV/trade | Cost/TP | Min Capital | Infra Needed |
|---------------|-----------|-------|---------|---------------|---------|-------------|-------------|
| Meme scalp (current) | 1-15min | 1%/0.5% | 35-45% | -0.21% | 17.8% | $10 | Current |
| ... | ... | ... | ... | ... | ... | ... | ... |

**Include at minimum:**
- Major scalp (TP 1-2%)
- Major swing (TP 5-15%)
- Meme swing (TP 5-15%)
- Funding rate capture
- Mean-reversion on majors
- Breakout momentum on majors
- Any other strategy you believe has positive EV

**For the top 2 strategies in your ranking: give us a concrete spec (indicators, entry/exit rules, timeframe, position sizing) that we could implement and test.**

---

### S17. The Uncomfortable Question

We've been operating under the assumption that there exists SOME strategy that will be profitable on Binance USDM at $10. But what if that assumption is wrong?

**At $10 bankroll with $5 Binance minimum notional:**
- Without leverage: position size = $2 (20% equity) → TP 5% = $0.10 profit
- With L=3: position size = $6 → TP 5% = $0.30 profit
- With L=8: position size = $16 → TP 5% = $0.80 profit

**Even with a positive edge of 0.5% per trade and 5 trades per day:**
- L=3: 5 × 0.005 × $6 = $0.15/day
- L=8: 5 × 0.005 × $16 = $0.40/day

**At what point does it become mathematically impossible to justify the operational cost (VPS $5/month, development time, monitoring) vs the expected return?** Is $10 a validation sandbox only, with the real question being "what bankroll makes this worth running?" If so, **what is that minimum bankroll number for the best alternative strategy you've identified in S16?**

---

## Updated Data Summary

| Metric | Previous Value | Updated Value (after R3 + R4 analysis) |
|--------|---------------|----------------------------------|
| EV per trade | -0.21% | **Likely more negative** (optimistic sim) |
| Simulation trust | "Borderline" | **Not trustworthy** for live decisions |
| Kelly sizing | N=5, e=20%, L=8 (8.0× bankroll) | **2× full-Kelly, 4× half-Kelly** — way too aggressive |
| Correct half-Kelly target | N/A | N×e×L ≤ 2.0 (e.g., N=3 e=8.5% L=8) |
| Slippage model | Gaussian cap 5bps | **Needs mixture distribution** (80/20 split) |
| SL exit slippage | Zero (stop-limit assumption) | **1.5× worse than market** (adverse selection) |
| Position correlation | Independent | **Correlated** — Kelly must treat as one joint bet |
| Strategy viability | "Needs fixes" | **Fundamental viability in question** — need alternative strategy research |
| Scalping edge (current) | Negative | **Negative** — confirmed across 4 rounds |
| Alternative strategies | Not evaluated | **Pending research** (S12-S17) |
