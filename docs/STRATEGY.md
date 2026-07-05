# Strategy: Meme-Coin Scalping with 8-Tier Signal Hierarchy

## Overview

The strategy generates LONG/SHORT signals on Binance USDM Futures perpetual contracts, primarily targeting meme coins and high-volatility assets. It uses a **tiered signal system** where the strongest signals are checked first, and only one signal is emitted per evaluation (first match wins).

**Philosophy:** Volume is the primary signal. Momentum confirms direction. Indicators (RSI, ADX, funding) add conviction. The regime filter (ADX) prevents trading in choppy markets.

## Signal Pipeline

```
Symbol to evaluate
    │
    ▼
┌──────────────┐     SKIP
│  Cooldown?   │──────────→ (wait 15s after last trade on this symbol)
└──────┬───────┘
       │ PASS
       ▼
┌──────────────┐
│  Fetch Klines│  GET /fapi/v1/klines?symbol=X&interval=5m&limit=60
│  (5m, 60)    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│  Calculate Indicators                │
│  • Volume ratio (current vs 30-candle avg)  │
│  • Momentum (ROC% over N candles)           │
│  • RSI (14-period)                          │
│  • ATR% (14-period)                         │
│  • ADX (14-period)                          │
│  • VWAP (60-candle)                         │
│  • Funding rate (live API)                  │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────┐     SKIP
│  ADX < 15?   │──────────→ (choppy market, no trade)
│  (not new    │           Exception: new listings bypass
│   listing)   │
└──────┬───────┘
       │ PASS (trending market)
       ▼
┌──────────────────────────────────────┐
│  Evaluate 8 Signal Tiers (top→bottom)│
│  First match wins → emit ScalpSignal │
│  No match → skip                     │
└──────────────────────────────────────┘
```

## The 8 Signal Tiers

### Tier 1: Volume Spike + Momentum (Strongest)

**Logic:** Abnormal volume confirms institutional/whale activity. Momentum confirms direction.

| Condition | LONG | SHORT |
|-----------|------|-------|
| Volume ratio | ≥ 2.0x | ≥ 2.0x |
| Momentum | > +0.08% | < -0.08% |

**Confidence:** `0.55 + min(0.15, vol_ratio/20) + min(0.15, |momentum|/5)`

Example: vol_ratio=4.0, momentum=0.5% → confidence = 0.55 + 0.15 + 0.10 = **0.80**

This is the bread-and-butter signal. It fires most often and has the highest expected edge.

### Tier 2: RSI Extreme + Volume Spike

**Logic:** Oversold/overbought RSI with volume confirmation suggests reversal.

| Condition | LONG | SHORT |
|-----------|------|-------|
| RSI | < 30 | > 70 |
| Volume ratio | ≥ 2.0x | ≥ 2.0x |

**Confidence:** `0.55 + min(0.15, vol_ratio/20)`

### Tier 3: Funding Rate Extreme + Momentum

**Logic:** Extreme funding rates create mean-reversion pressure. When shorts pay longs excessively (negative funding), the cost of being short incentivizes closing → price rises.

| Condition | LONG | SHORT |
|-----------|------|-------|
| Funding rate | < -0.001 | > +0.001 |
| Momentum | > +0.08% | < -0.08% |

**Confidence:** `0.55 + min(0.20, |funding| × 100)`

### Tier 4: New Listing Aggressive

**Logic:** Newly listed coins have extreme volatility and no established support/resistance. We trade pure momentum.

**Relaxed conditions** (no volume spike required):

| Condition | Confidence |
|-----------|------------|
| \|Momentum\| > 0.08% | 0.56 + min(0.15, \|mom\|/2) |
| Volume ≥ 1.3x AND \|Momentum\| > 0.03% | 0.56 + min(0.10, \|mom\|/3) |

**Important:** New listings bypass the ADX regime filter entirely.

### Tier 5: Consecutive Candle Run

**Logic:** 3+ consecutive same-direction candles with above-average volume suggest strong directional conviction.

| Condition | BOTH DIRECTIONS |
|-----------|-----------------|
| Consecutive candles | ≥ 3 same direction |
| Volume ratio | ≥ 1.2x |

**Confidence:** `0.56 + min(0.10, consecutive × 0.03)`

### Tier 6: High Volatility Momentum

**Logic:** When ATR is very high, even small momentum moves can be profitable with tight stops.

| Condition | BOTH DIRECTIONS |
|-----------|-----------------|
| ATR% | > 1.0% |
| Momentum | meets threshold |
| Volume ratio | ≥ 1.1x |

**Confidence:** `0.56 + min(0.10, ATR% / 5)`

### Tier 7: Daily Trend Following

**Logic:** Align with the broader daily trend when 1m momentum confirms.

| Condition | BOTH DIRECTIONS |
|-----------|-----------------|
| \|24h price change\| | > 5% |
| 1m momentum | aligned with daily |
| Volume ratio | ≥ 1.1x |

**Confidence:** `0.56 + min(0.15, \|24h_change\| / 20)`

### Tier 8: VWAP Reversion + RSI

**Logic:** When price is near VWAP (fair value) and RSI is neutral, a momentum push can start a trend.

| Condition | BOTH DIRECTIONS |
|-----------|-----------------|
| Price vs VWAP | within ±0.3% |
| RSI | 40-60 (neutral) |
| Momentum | meets threshold |
| ADX | > trending threshold |

**Confidence:** `0.57 + min(0.10, |price_vs_vwap| / 0.1)`

## Post-Processing

After any tier matches:
1. **Confidence cap:** `min(confidence, 0.90)` — never claim >90% certainty
2. **Threshold check:** If `confidence < 0.54` → reject signal (too weak)
3. **Cooldown:** Mark 15-second cooldown for this symbol
4. **Emit:** Return `ScalpSignal` with side, entry price, confidence, reason, and indicator values

## Active Configuration (YAML overrides code defaults)

| Parameter | Code Default | YAML Override | Rationale |
|-----------|-------------|---------------|-----------|
| `kline_interval` | 1m | **5m** | Less noise, more reliable signals |
| `momentum_candles` | 5 | **3** | Faster detection |
| `momentum_threshold` | 0.15% | **0.08%** | More sensitive (more trades) |
| `confidence_threshold` | 0.55 | **0.54** | Slightly more permissive |
| `adx_trending` | 20 | **15** | More markets pass regime filter |
| `take_profit_pct` | 0.40% | **1.0%** | Wider target for better R:R |
| `stop_loss_pct` | 0.20% | **0.50%** | Wider stop to avoid premature exits |
| `max_hold_sec` | 300 | **900** | Give trades 15 min to develop |

## Signal Frequency Distribution (observed in practice)

| Tier | Estimated % of signals | Notes |
|------|----------------------|-------|
| Tier 1: Vol+Momentum | ~40% | Most common, most reliable |
| Tier 4: New Listing | ~20% | Very volatile, high variance |
| Tier 5: Candle Run | ~15% | Moderate reliability |
| Tier 6: High Vol | ~10% | Often overlaps with Tier 1 |
| Tier 7: Daily Trend | ~8% | Rare on 5m timeframe |
| Tier 2: RSI Extreme | ~4% | Rare, often good |
| Tier 3: Funding | ~2% | Very rare |
| Tier 8: VWAP | ~1% | Rarest, weakest |

## Key Questions for Reviewers

1. **Are 8 tiers too many?** Does having weaker tiers (6-8) dilute the edge from strong tiers (1-3)?
2. **Should we weight exits by signal tier?** E.g., Tier 1 signals get wider stops, Tier 8 gets tighter stops?
3. **Is momentum threshold 0.08% too sensitive?** On 5m candles, 0.08% is barely a move. Are we catching noise?
4. **Should RSI use Wilder's smoothing** instead of simple average? The current implementation uses simple average RSI which is less smooth.
5. **Is the ADX threshold of 15 too low?** Standard is 20-25. At 15, we're allowing borderline choppy markets.
