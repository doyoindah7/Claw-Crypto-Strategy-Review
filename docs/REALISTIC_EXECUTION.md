# Realistic Execution Simulation

## Why Realistic Paper Trading?

Naive paper trading fills at mid/last price with 100% certainty. This creates **false optimism**:

| Factor | Naive Paper | Reality | Impact |
|--------|------------|---------|--------|
| Spread | Ignored | LONG fills at ASK, SHORT fills at BID | Hidden cost on every trade |
| Slippage | Ignored | Market orders eat through book levels | Worse fill than expected |
| Fill probability | 100% | ~97% (rejections happen) | Missed trades, lost alpha |
| Partial fills | Never | ~8% of orders partially fill | Smaller position = smaller profit |
| Fees | Maker (0.02%) | Taker (0.05%) for market orders | 2.5× fee impact |

**If the bot can't profit with realistic simulation, it WILL lose money in live trading.**

## Simulation Model

### Entry Execution Pipeline

```
Intended Order (side, price, notional)
    │
    ▼
┌────────────────────┐   REJECT
│ Min Notional Check │────────→ ($5 minimum on Binance)
│ notional < $5?     │
└────────┬───────────┘
         │ PASS
         ▼
┌────────────────────┐   REJECT
│ Fill Probability   │────────→ 3% chance (random reason)
│ random() > 0.97?   │
└────────┬───────────┘
         │ PASS (97%)
         ▼
┌────────────────────┐
│ Calculate Spread   │  effective_spread = base × meme_mult × new_listing_mult
│                    │  half_spread = effective_spread / 2
│                    │
│  LONG: fill at ASK = price × (1 + half_spread/100%)
│  SHORT: fill at BID = price × (1 - half_spread/100%)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Add Slippage       │  slippage_bps = min(max, |Gauss(mean=1.5, std=1.0)|)
│                    │  Always adverse (worse for us)
│                    │
│  LONG: fill_price × (1 + slip_pct/100%)
│  SHORT: fill_price × (1 - slip_pct/100%)
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Partial Fill?      │  8% chance → fill_ratio = uniform(0.6, 0.99)
│ (8% probability)   │  92% chance → fill_ratio = 1.0
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│ Calculate Fee      │  fee = fill_notional × 0.05% (taker)
└────────┬───────────┘
         │
         ▼
   ExecutionResult (fill_price, spread_cost, slippage_bps, fee_usd, fill_ratio)
```

### Exit Execution

Exit follows the same model with two key differences:

1. **SL_HIT / TP_HIT:** Use **exact trigger price**, no spread or slippage
   - Rationale: Stop-limit orders on the exchange guarantee fill at trigger level
   - Only taker fee is charged (one side)
   
2. **MAX_HOLD / TRAILING_STOP:** Use full `simulate_exit()` with spread + slippage
   - These are market orders with no price guarantee
   - Exit fill probability = 99% (slightly higher than entry)
   - No partial fills on exit

### Effective Spread Calculation

```
effective_spread_bps = base_spread_bps × meme_multiplier × new_listing_multiplier
```

| Symbol Type | Base | Meme | New | Effective | Cost per $10 trade |
|-------------|------|------|-----|-----------|-------------------|
| Major (BTC, ETH) | 5.0 bps | 1.0× | — | 5.0 bps | $0.0025 |
| Meme (PEPE, DOGE) | 5.0 bps | 2.5× | — | 12.5 bps | $0.0063 |
| New listing (non-meme) | 5.0 bps | 1.0× | 2.0× | 10.0 bps | $0.0050 |
| New listing (meme) | 5.0 bps | 2.5× | 2.0× | **25.0 bps** | $0.0125 |

**Half spread** is applied (one side of the bid-ask spread):
- Entry LONG: pays half spread (fills at ASK)
- Entry SHORT: pays half spread (fills at BID)
- Exit LONG: pays half spread (fills at BID)
- Exit SHORT: pays half spread (fills at ASK)

### Total Round-Trip Cost

For a round-trip trade (entry + exit) on a meme coin:

| Cost Component | Entry | Exit (SL/TP) | Exit (Market) |
|----------------|-------|-------------|---------------|
| Half spread | 6.25 bps | 0 | 6.25 bps |
| Slippage | ~1.5 bps | 0 | ~1.5 bps |
| Taker fee | 5.0 bps | 5.0 bps | 5.0 bps |
| **Total** | **12.75 bps** | **5.0 bps** | **12.75 bps** |

**SL/TP exit round-trip total:** 12.75 + 5.0 = **17.75 bps ≈ 0.178%**
**Market exit round-trip total:** 12.75 + 12.75 = **25.5 bps ≈ 0.255%**

### Impact on Profitability

With TP=1.0% and SL=0.5% on a meme coin:

| Scenario | Gross PnL | Round-trip Cost | Net PnL |
|----------|-----------|----------------|---------|
| TP hit | +1.000% | -0.178% | **+0.822%** |
| SL hit | -0.500% | -0.178% | **-0.678%** |
| Trailing stop at +1.5% | +1.500% | -0.255% | **+1.245%** |

**Required win rate for breakeven:**
```
breakeven_winrate = |avg_loss| / (avg_win + |avg_loss|)
                  = 0.678 / (0.822 + 0.678)
                  = 0.452 = 45.2%
```

If we can win >45.2% of trades with these parameters, we're profitable. The strategy needs to maintain at least a ~45% win rate after realistic costs.

### PnL Decomposition

Every trade records:
- **`gross_pnl_pct`**: PnL based on fill prices (includes spread + slippage, excludes fees)
- **`fee_impact_pct`**: Total fees as a percentage of notional
- **`pnl_pct`**: `gross_pnl_pct - fee_impact_pct` (the actual bottom line)

This decomposition is critical for understanding WHERE losses come from:
- If `gross_pnl_pct` is positive but `pnl_pct` is negative → strategy edge exists but is eaten by fees
- If `gross_pnl_pct` is negative → the signal itself is wrong

## Questions for Reviewers

1. **Is our slippage model realistic?** We use Gaussian(1.5, 1.0) bps capped at 5 bps. In practice, slippage for meme coins during high volatility can be 10-20+ bps. Should we model fat tails?
2. **Should SL/TP exits also have slippage?** On Binance, stop-market orders (not stop-limit) can slip. Our model assumes stop-limit. Should we add a "stop type" configuration?
3. **Is 3% rejection rate accurate?** This was estimated. In live trading, rejection reasons vary (insufficient margin, price limits, etc.). Should rejections be correlated with market conditions?
4. **Partial fills on entry only?** We model partial fills on entry (8%) but always full fills on exit. In reality, exit partial fills can happen, especially for large positions in illiquid markets.
5. **Spread multiplier model too simplistic?** We use fixed 2.5× for meme coins, but real spreads vary by time of day, volatility, and liquidity. Should we use a dynamic spread model?
