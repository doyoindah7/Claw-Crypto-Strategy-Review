# Insight Round 3 — Implementation Path

> **Context**: Round 1 identified structural problems. Round 2 got quantitative answers. Key finding: **current EV is -0.21% per trade (NEGATIVE)**. Round 3 focuses on *how to implement the fixes* and *validate before going live*.

---

## Critical New Fact

Claude calculated our current EV per trade:
```
EV = 0.4 × 0.95% - 0.6 × 0.65% - 0.2% = -0.21%
```
**This is structurally negative. No leverage can fix a negative edge.** The priority is achieving positive edge BEFORE optimizing anything else.

---

## Replay Validation (THE critical blocker)

**R1.** Claude said: replay historical entries against new TP/SL to measure WR elasticity. Our trade DB (SQLite, 40+ columns) records every entry with timestamp, symbol, side, confidence, signal_reason. But we have NO automated replay pipeline.

**Design the minimum viable replay system:**
- Input: trade entries from SQLite (symbol, entry_time, side)
- Process: fetch historical klines from Binance API for each entry symbol/time, simulate TP/SL hits using kline high/low
- Output: WR, avg win/loss, EV per TP/SL combination

**What's the simplest implementation? Can we do this with just Binance REST API klines, or do we need tick data? What time window after entry should we simulate (15min? 1hr? 4hr?)**

**R2.** Our kline interval is 5m. Simulating SL hits using 5m kline low/high has the same problem Claude flagged in F9 — wicks inside the candle aren't visible.

**Is 5m kline granularity sufficient for replay, or do we need 1m? What's the expected error in WR measurement from using 5m vs 1m klines for stop-loss hit detection?**

**R3.** How many historical trades do we need for a statistically valid replay? If we have ~200 trades in the DB, is that enough to validate TP 3%/SL 2% with ±5% confidence interval on WR?

---

## Multiplicative Confidence Formula (F4 Implementation)

**R4.** Proposed formula:
```python
vol_score = min(1, vol_ratio / 5)
mom_score = min(1, |momentum| / 1.0)
confidence = 0.50 + 0.35 * (vol_score * mom_score)
```

This changes ALL tier confidence calculations. Currently each tier has its own formula. **Should we apply this multiplicative logic to ALL tiers, or only Tier 1 (where it matters most)?** Tier 2 (RSI+Volume) doesn't use momentum — does it need a different AND-gate?

**R5.** The caps: vol at 5x, momentum at 1.0%. Our data: typical vol_ratio is 2-4x, typical momentum is 0.1-0.5%. **Is the cap too high? Should it be vol/3 and momentum/0.5% to spread the scoring better within our actual data range?**

**R6.** Threshold at 0.60. Claude said WR needs >53% for profitability with the new TP/SL. But the multiplicative formula already filters more aggressively. **Should threshold be 0.60 or 0.55? What's the tradeoff — too few signals vs taking marginal trades?**

---

## Transition Plan: 20x → 8x

**R7.** We can't just flip leverage from 20x to 8x while keeping 5 concurrent positions. At 20% equity × 8x = $16 notional per position on $10 bankroll. Binance minimum notional is $5. With 5 positions: $80 total notional, $10 margin — 100% of bankroll deployed.

**Is 20% equity sizing too aggressive at 8x? Should we drop to 10% equity or reduce max positions to 3? What's the Kelly-optimal sizing for WR 45%, TP 3%, SL 2%?**

**R8.** During transition, do we run both parameter sets simultaneously (A/B) or switch completely? A/B means splitting the $10 bankroll which is already tiny.

**Is A/B testing feasible at $10, or should we just switch and compare against historical baseline?**

---

## MFE Measurement (F3 follow-up)

**R9.** Claude suggested measuring Max Favorable Excursion from historical entries. Our bot already tracks `max_favorable_pct` in PaperPosition — but this is for the CURRENT tight TP/SL, so trades get closed before reaching MFE.

**How do we measure true MFE? Do we: (a) modify the bot to NOT exit on TP/SL and just track price for N minutes, or (b) use the replay system to calculate MFE from klines? Which is more practical?**

---

## Stop-Market on Exchange (F9/F10 follow-up)

**R10.** Confirmed: Binance USDM supports stop-market with `workingType=MARK_PRICE`. This eliminates the polling SL problem entirely.

**Implementation question**: Our bot is currently paper-trading only (simulates everything in memory). To use exchange stop orders, we need to switch to live trading. **Is there a way to use stop-market orders in testnet mode for validation before risking real funds?** How does Binance testnet handle stop-market?

**R11.** If we switch to stop-market on exchange: our current SL logic runs in the main loop (check price → close position). The new flow would be: open position → place stop-market on exchange → monitor for TP hit only (still polling).

**Does this reduce our polling requirement enough that 2s intervals are acceptable? We only need to check TP, not SL — TP overshoot is profit, not loss.**

---

## Bayesian/Sequential Testing (F8 follow-up)

**R12.** Claude said classical A/B needs ~773 trades per group (unrealistic for $10 bot). Suggested Bayesian/sequential testing.

**Give us a concrete Bayesian stopping rule we can implement.** E.g.: "Stop after N trades if posterior P(WR_A > WR_B) > 95%". What prior should we use? How many trades minimum before we can stop early?

---

## The One-Pager: What To Build Next

**R13.** Given everything (EV negative, replay needed, multiplicative formula, 8x leverage, stop-market on exchange):

**Give us a ranked implementation checklist — what to build first, what can wait. Each item should be one sentence. Example:**

1. Build replay pipeline → validate TP3%/SL2% WR on historical entries
2. If WR > 44% in replay → switch to multiplicative confidence + threshold 0.60
3. ...

**What's the sequence, and what's the go/no-go gate between each step?**

---

## Paper Trading Environment — Is Our Simulation Realistic?

Before we trust any metric from this system, you need to know EXACTLY how our paper bot simulates reality. **Review this setup and tell us: where is our simulation too optimistic? Where is it too pessimistic? What specific changes would make it more realistic?**

### Infrastructure

| Component | Setup |
|-----------|-------|
| Runtime | Python 3.x, single-process, **synchronous** (no asyncio) |
| VPS | $5 VPS, runs via systemd (`claw-realistic` service) |
| Threading | Main loop (bot) + 1 daemon thread (HTTP dashboard) |
| State sharing | No locks — dashboard slider writes can race with main loop reads |
| Crash recovery | **None for open positions** — only closed trades persist to SQLite |

### Price Feed

| Aspect | Implementation |
|--------|---------------|
| Source | Binance REST API (`/fapi/v1/ticker/price`) |
| Polling interval | **2 seconds** (hardcoded in main loop) |
| Kline source | `/fapi/v1/klines` (5m interval, 60 candles per fetch) |
| WebSocket | **Not used** |
| Order book | **Not used** — spread is simulated, not read from L2 data |
| Rate limit | 50ms min between requests, monitor weight header |

### Execution Simulation (Entry)

```
Order → Min Notional Check ($5) → Fill Probability (97%) →
Apply Spread → Add Slippage → Partial Fill Check (8%) → Fee
```

| Parameter | Value | Our Concern |
|-----------|-------|-------------|
| Base spread | 5 bps | Too low for some meme coins? |
| Meme multiplier | 2.5× (→ 12.5 bps) | Fixed — doesn't vary with time/vol |
| New listing multiplier | 2.0× on top of meme (→ 25 bps) | |
| Slippage model | Gaussian(μ=1.5, σ=1.0) bps, **cap 5 bps** | **Way too tame?** Real meme slippage can be 10-50+ bps during volatility |
| Fill probability | 97% (3% rejected) | Accurate? |
| Partial fill | 8% chance, 60-99% fill ratio | Entry only — exit always fills 100% |
| Fee | 0.05% taker per side | Accurate (Binance USDM standard) |
| Latency simulation | Gaussian(μ=8ms, σ=4ms), min 2ms | **Not applied to price** — only logged, doesn't shift fill price |

### Execution Simulation (Exit) — TWO MODES

**Mode 1: SL/TP Hit (stop-limit simulation)**
- Exit at **exact trigger price** — no spread, no slippage
- Fee: 0.05% taker
- Rationale: simulates exchange stop-limit order
- **CRITICAL CONCERN**: In reality, stop-limit can **fail to fill** if price gaps through. We never model this. Also, we're not using stop-limit on exchange — we're polling and checking in software, so the "exact trigger price" assumption may be wrong.

**Mode 2: Max Hold / Trailing Stop (market order simulation)**
- Full spread + slippage + fee
- Exit fill probability: 99%
- No partial fills on exit
- This is more realistic

### SL Overshoot Handling

Our SL check runs every 2 seconds. We check `current_price` against SL level. If price has moved past SL between checks:
- We close at `current_price`, NOT at the SL trigger price
- This creates the observed overshoot: SL 0.5% → actual exits at 0.72%, 0.82%, 1.60%
- **We do NOT use kline high/low to detect intra-poll wicks** — only current_price

### What We KNOW Is Wrong

1. **Slippage model too tame**: Gaussian capped at 5 bps. Real meme slippage during dumps is 10-50+ bps. This makes our cost model **optimistic**.
2. **Spread is static**: 5 bps × 2.5 for memes. Real spread varies by time of day, volatility, and liquidity. Sometimes wider, sometimes narrower.
3. **SL/TP exits have zero slippage**: We assume stop-limit fills exactly at trigger. In reality, stop-market (which we should use) has slippage, and stop-limit can fail to fill.
4. **No latency impact on price**: We simulate latency timing but don't use it to shift fill price. Real market orders execute after network delay — price may have moved.
5. **No order book depth**: We can't detect thin liquidity, spoofing, or book imbalances.
6. **Exit partial fills ignored**: We assume 100% fill on exit. In reality, large positions in illiquid markets can get partial fills.
7. **Rejection reasons are random**: Our 3% rejection picks random reasons. In reality, rejections correlate with market conditions (more likely during high volatility).
8. **No correlation between positions**: 5 concurrent LONG meme positions can all crash together. Our PnL treats them as independent.

### What We Think Is Correct

1. **Taker fee 0.05% per side**: Matches Binance USDM standard tier
2. **Spread direction logic**: LONG fills at ASK, SHORT fills at BID (correct)
3. **PnL decomposition**: We separately track gross_pnl, fee_impact, and net_pnl
4. **Runtime config snapshots**: Every trade records the SL/TP/sizing AT OPEN TIME, not current slider value
5. **Minimum notional enforcement**: $5 Binance minimum checked on every entry
6. **Fill probability independent of order size**: Should probably scale with notional

### R14. The Realism Audit

**Given the full environment description above, rate each simulation aspect on a scale: OPTIMISTIC / REALISTIC / PESSIMISTIC. For each OPTIMISTIC item, quantify how much it inflates our win rate or underestimates our costs. Specifically:**

1. **Slippage cap at 5 bps**: How much does this underestimate real slippage on meme coins? What's a more realistic distribution?
2. **Zero slippage on SL/TP exits**: We're assuming stop-limit fills perfectly. You said use stop-market. If we switch to stop-market, what slippage should we add to SL exits?
3. **Static spread**: How much does real spread vary? Should we fetch live bid-ask?
4. **No latency price impact**: How much does 50-200ms real-world latency actually cost on a 2s polling bot?
5. **Independent position PnL**: If 5 meme LONGs crash together 30% of the time, how does that change our ruin probability?

**Bottom line: is our paper trading environment trustworthy enough for the metrics we're using to make decisions? Or are we making decisions based on inflated numbers?**
