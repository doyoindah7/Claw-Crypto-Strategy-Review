# Performance Metrics — Reference Data for AI Analysis

> All metrics are from realistic paper trading simulation (not live). No raw trade logs are available on this system — these are aggregated observations documented during bot operation.

---

## 1. Aggregate Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Win rate | 35-45% | Observed across multiple sessions |
| Average win (net) | +0.7% to +1.2% | After fees, spread, slippage |
| Average loss (net) | -0.5% to -0.8% | After fees, spread, slippage |
| Average loss (SL hit) | -0.6% to -0.8% | Config SL 0.5% + fee drag |
| Worst SL exit | -1.60% | Polling overshoot + fee |
| Typical SL exit | -0.72% to -0.82% | 0.5% SL + 0.10% fee + ~0.2% overshoot |
| Expectancy | **-0.21% per trade (NEGATIVE)** | Structurally unprofitable (confirmed by AI analysis) |
| Session duration | 2-8 hours | Paper trading sessions |
| Starting bankroll | $10 | Fixed for all sessions |

## 2. Cost Structure (Per Round-Trip Trade)

| Cost Component | Value | Calculation |
|----------------|-------|-------------|
| Taker fee (entry) | 0.05% of notional | Binance USDM standard |
| Taker fee (exit) | 0.05% of notional | SL/TP/market exit |
| Total fee | 0.10% of notional | 2.0% of margin at 20x |
| Spread (standard meme) | 12.5 bps (0.125%) | 5bps base × 2.5 meme multiplier |
| Spread (new listing meme) | 25 bps (0.25%) | 5bps base × 2.5 meme × 2.0 new |
| Slippage (avg) | 1.5 bps | Gaussian(μ=1.5, σ=1.0) |
| Slippage (worst case) | 5 bps | Hard cap in simulation |
| **Round-trip cost (SL/TP exit)** | **17.75 bps (0.178%)** | Fee + spread + 2× slippage |
| **Round-trip cost (market exit)** | **25.5 bps (0.255%)** | Higher spread + slippage on exit |

### Cost as % of TP Target

| TP Target | Round-trip cost | Cost/TP ratio | Viability |
|-----------|----------------|---------------|-----------|
| 1.0% (current) | 0.178% | 17.8% | ❌ Marginally viable |
| 1.5% | 0.178% | 11.9% | ⚠️ Borderline |
| 3.0% (Fifteen-inspired) | 0.178% | 5.9% | ✅ Comfortable |
| 5.0% | 0.178% | 3.6% | ✅ Strong |
| 8.0% (Fifteen original) | 0.178% | 2.2% | ✅ Very strong |

### Breakeven Win Rate by TP/SL

| TP | SL | R:R | Round-trip cost | Breakeven WR |
|----|-----|-----|-----------------|--------------|
| 1.0% | 0.5% | 2:1 | 0.178% | 45.2% |
| 1.5% | 1.0% | 1.5:1 | 0.178% | 44.4% |
| 2.0% | 1.5% | 1.33:1 | 0.178% | 46.2% |
| 3.0% | 2.0% | 1.5:1 | 0.178% | 42.8% |
| 3.0% | 2.5% | 1.2:1 | 0.178% | 48.1% |
| 5.0% | 3.0% | 1.67:1 | 0.178% | 40.7% |
| 8.0% | 7.6% | 1.05:1 | 0.178% | 49.3% |

Formula: `BE_WR = (SL + cost) / (TP + SL + cost)`

## 3. Signal Tier Distribution

| Tier | Name | Signal Frequency | Confidence Range | Notes |
|------|------|-----------------|------------------|-------|
| 1 | VolSpike+Momentum | ~40% | 0.55-0.85 | Bread and butter |
| 2 | RSI+Volume | ~4% | 0.55-0.70 | Rare, often good |
| 3 | Funding+Momentum | ~2% | 0.55-0.75 | Very rare |
| 4 | New Listing | ~20% | 0.56-0.71 | High variance, most damaging |
| 5 | ConsecCandles | ~15% | 0.56-0.66 | Moderate reliability |
| 6 | HighVol+Momentum | ~10% | 0.56-0.66 | Overlaps Tier 1 |
| 7 | DailyTrend | ~8% | 0.56-0.71 | Rare on 5m |
| 8 | VWAP+RSI | ~1% | 0.57-0.67 | Rarest, weakest |

**Per-tier profitability**: NOT tracked. This is a critical gap identified by Claude (Q1 response). The bot only tracks aggregate WR, not WR per tier.

## 4. SL Overshoot Data

| Config SL | Observed SL Exit | Overshoot | Cause |
|-----------|-----------------|-----------|-------|
| 0.5% | 0.72% | +0.22% | Fee drag (0.10%) + polling delay |
| 0.5% | 0.82% | +0.32% | Fee + late detection |
| 0.5% | 1.60% | +1.10% | Flash dump, price gapped through SL between polls |

**Root cause**: 2-second polling interval. At meme coin volatility, price can move 0.5%+ in <1 second. SL is checked against current price, not against price trajectory since last check.

## 5. Polymarket Fifteen Reference (Profitable Bot)

| Parameter | Fifteen (PM) | Crypto Bot (Binance) | Delta |
|-----------|-------------|---------------------|-------|
| Signal type | 1 (EMA+ROC) | 8 tiers | +7 signal types |
| TP | 8.0% | 1.0% | -87.5% |
| SL | 7.6% | 0.5% | -93.4% |
| R:R | 1.05:1 | 2:1 | Tighter |
| Momentum threshold | 0.002% | 0.08% | 40× less sensitive |
| Leverage | None | 20x | +20x |
| Fee round-trip | 25 bps | 10 bps | -60% |
| Effective spread | 0 (CLOB) | 12.5-25 bps | +∞ |
| Total cost round-trip | 25 bps | 17.75-25.5 bps | Comparable |
| Cost/TP ratio | 3.1% | 17.8% | 5.7× worse |
| WR (estimated) | ~40% | 35-45% | Similar |
| Price feed | WebSocket (sub-ms) | REST polling (2s) | Degraded |
| Execution | FOK (instant) | Simulated market | Degraded |

**Key insight**: Cost/TP ratio is the #1 differentiator. Fifteen's cost is 3.1% of TP target; crypto bot's cost is 17.8% — nearly 6× worse. Same dollar cost, but TP target is 8× smaller.

## 6. Active Configuration

| Parameter | Code Default | YAML Override |
|-----------|-------------|---------------|
| kline_interval | 1m | 5m |
| momentum_candles | 5 | 3 |
| momentum_threshold | 0.15% | 0.08% |
| confidence_threshold | 0.55 | 0.54 |
| adx_trending | 20 | 15 |
| take_profit_pct | 0.40% | 1.0% |
| stop_loss_pct | 0.20% | 0.50% |
| max_hold_sec | 300 | 900 |
| leverage | — | 20x |
| position_size_pct | — | 20% equity |
| max_positions | — | 5 |
| cooldown_sec | — | 15 |

## 7. Market Selection

| Filter | Criteria |
|--------|----------|
| Min volume 24h | $1M |
| Min volatility | Tracked via ATR% |
| ADX filter | > 15 (unless new listing) |
| Scoring | volume(0-30) + volatility(0-30) + new_listing(0-50) |
| Max markets | Top 30 by score |
| Total universe | ~573 Binance USDM perpetuals |
| Typical active | 25-35 markets per scan |

## 8. Data Gap Analysis

What we DON'T have but need:

| Data Point | Why It Matters | How to Get It |
|-----------|----------------|---------------|
| Per-tier WR | Validate/cull weak tiers | Add tier field to trade DB |
| Per-confidence-bucket WR | Fix confidence formula | Query existing DB by confidence |
| Slippage distribution | Validate cost model | Already tracked in PaperPosition |
| Time-of-day performance | Session-dependent params | Add hour field to trade DB |
| Correlated positions | Risk of simultaneous SL | Track position correlation |
| Time-to-TP distribution | Validate max_hold_sec | Already tracked as hold_sec |
| Meme vs major WR | Market type filter | Add is_meme flag to trade DB |

The bot's SQLite database (`trade_db.py`) tracks 40+ columns per trade including: symbol, side, entry/exit price, PnL decomposition (fee, spread, slippage), confidence, signal_reason, hold_sec, leverage, etc. **This data exists on the running bot's server but is not available in this review repository.**

---

## 9. AI Analysis Findings (Round 2)

> Findings from Claude's analysis of insight.md + insight_followup.md

### Current EV Calculation

```
EV per trade = WR × avg_win - (1-WR) × avg_loss - round_trip_cost
            = 0.40 × 0.95% - 0.60 × 0.65% - 0.20%
            = 0.38% - 0.39% - 0.20%
            = -0.21%
```
**Conclusion: The strategy is structurally negative expectancy. No leverage can fix this.**

### Proposed Parameter Set (Claude, Round 2)

| Parameter | Current | Proposed | Rationale |
|-----------|---------|----------|-----------|
| TP | 1.0% | 3.0% | Reduce cost/TP ratio from 17.8% → 5.9% |
| SL | 0.5% | 2.0% | Wider stops survive noise |
| Leverage | 20x | 8x | Reduce ruin factor from 20 → 8 |
| Position size | 20% equity | 20% equity | Same |
| Confidence threshold | 0.54 (additive) | 0.60 (multiplicative) | AND-gate filter |
| ADX | 15 | 18 | Compromise pending A/B test |
| Momentum threshold | 0.08% fixed | max(0.03%, 0.04×ATR%) | ATR-adaptive with floor |
| Max positions | 5 | 5 | Same |

**Breakeven WR at proposed params: 44% (using `(2+0.2)/5`)**
**Estimated WR at proposed params: 38-45% (needs replay validation)**

### Multiplicative Confidence Formula (AND-Gate)

```python
vol_score = min(1, vol_ratio / 5)
mom_score = min(1, |momentum| / 1.0)
confidence = 0.50 + 0.35 * (vol_score * mom_score)
```

- Weak signal (vol=2x, mom=0.08%): 0.4 × 0.08 = 0.032 → confidence = 0.511 → **REJECTED** (below 0.60)
- Strong signal (vol=4x, mom=0.5%): 0.8 × 0.5 = 0.40 → confidence = 0.64 → **ACCEPTED**

### Ruin Math

`worst_case_loss_fraction = N × e × L × SL%`
- Current (N=5, e=0.2, L=20, SL=0.5%): 5 × 0.2 × 20 × 0.005 = 10% → seems ok
- But with SL overshoot (0.8% actual): 5 × 0.2 × 20 × 0.008 = 16%
- Proposed (N=5, e=0.2, L=8, SL=2%): 5 × 0.2 × 8 × 0.02 = 16% → same dollar risk, wider stops

### Key Blocked Questions (Need Replay)

1. **WR at TP 3%/SL 2%** — estimated 38-45%, but only replay can confirm
2. **MFE distribution** — what % of trades reach 3%+ favorable?
3. **Time-to-TP at 3%** — how long do we hold on average?
4. **Per-tier WR** — which tiers are negative vs positive expectancy?

### Minimum Bankroll for Profitability

At TP 3%/SL 2%/WR 45%, EV = 0.05% per trade:
- For $1/day profit: $1000 bankroll needed (10 trades/day × 20% sizing)
- At $10 bankroll: this is a validation phase, not a profit phase

---

## 10. AI Analysis Findings (Round 3)

> Critical findings: simulation is systematically optimistic, sizing is 2× full-Kelly

### Simulation Realism Verdict

| Simulation Aspect | Verdict | Impact |
|-------------------|---------|--------|
| Slippage cap 5bps | **OPTIMISTIC** | Real cost 30-50% higher than modeled. EV more negative than -0.21% |
| Zero slippage on SL/TP exits | **OPTIMISTIC** | SL exits have adverse selection — slippage 1.5× worse than market orders |
| Static spread | **OPTIMISTIC (mild)** | Spread widens during volatility, exactly when stops trigger |
| No latency price impact | **OPTIMISTIC (minor)** | Second-order effect at 2s polling |
| Independent position PnL | **OPTIMISTIC (major for risk)** | Doesn't bias WR but drastically underestimates drawdown variance |

**Bottom line: EV -0.21% is likely an UPPER BOUND. Real EV is more negative. Simulation is NOT trustworthy for live capital decisions.**

### Slippage Fix (Proposed)

Replace Gaussian(μ=1.5, σ=1.0) cap 5bps with **mixture distribution**:
- 80% of time (normal): Gaussian(μ=3, σ=2) cap 8bps
- 20% of time (volatile): Gaussian(μ=20, σ=10) cap 60bps

For SL exits specifically: multiply slippage by 1.5× due to adverse selection.

### Kelly Sizing Correction

Original proposal: N=5, e=20%, L=8 → total notional = **8.0× bankroll** — this is 2× full-Kelly, 4× half-Kelly.

Kelly criterion for correlated positions: treat N concurrent meme positions as **one joint bet**.

```
f* = (p×TP - q×SL) / (TP×SL) = (0.45×0.03 - 0.55×0.02) / 0.0006 = 4.17 (full-Kelly)
Half-Kelly target: ~2.0× bankroll
Constraint: N × e × L ≤ 2.0
```

Valid configurations at half-Kelly:

| N | e | L | N×e×L | Notional/pos ($10 bankroll) | Above $5 min? |
|---|---|-------|-------|-----|------|
| 3 | 8.5% | 8 | 2.04 | $6.80 | ✅ Barely |
| 2 | 13% | 8 | 2.08 | $10.40 | ✅ Yes |
| 1 | 25% | 8 | 2.00 | $20.00 | ✅ Comfortable |
| 3 | 20% | 3 | 1.80 | $6.00 | ✅ Barely |
| 2 | 33% | 3 | 1.98 | $10.00 | ✅ Yes |

### Replay Pipeline Specs (Confirmed)

| Parameter | Value |
|-----------|-------|
| Kline granularity | **1m** (not 5m — nearly free, eliminates biggest error source) |
| Simulation window | max_hold_time from config (currently 900s = 15 min) |
| Sample size for ±5% CI | 379 trades |
| Current sample (~200 trades) | ±7% CI — enough for clear signals, not for 40-48% zone |
| Data source | Binance REST API `/fapi/v1/klines` (1m, 240 candles = 4hr per call) |

### Implementation Checklist (Ranked, Claude R3)

1. Build replay pipeline (1m klines) — no capital needed
2. Replay ~200 trades at TP3%/SL2% → **GATE: WR ≥50%** (above 44% breakeven + CI)
3. Recompute multiplicative confidence + sweep threshold 0.50-0.70 → **GATE: expected profit positive in replay**
4. Fix position sizing to half-Kelly (N×e×L ≤ 2.0) → **GATE: sizing within fractional-Kelly**
5. Validate stop-market mechanics on testnet → **GATE: order placement/trigger/cancel work correctly**
6. Switch exit simulation to stop-market realistic (add slippage) + reduce polling to TP-only
7. Fix known simulation flaws (slippage mixture, SL exit slippage, position correlation)
8. Switch fully to new params (no A/B at $10), monitor forward vs replay baseline
9. Use Bayesian sequential testing for future parameter iteration

### Confidence Formula Calibration

- Apply AND-gate generically: `confidence = base + boost_scale × (score_1 × score_2 × ...)`
- Each tier supplies its own component scores (e.g., Tier 2 uses RSI-extremity × volume, not momentum)
- Calibrate caps from **90th/95th percentile of winning trades' vol_ratio and momentum** (not overall distribution)
- Sweep threshold 0.50-0.70, optimize for **total expected profit** (WR×TP - (1-WR)×SL - cost × trade_count), not just WR
