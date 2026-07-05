# Risk Management

## Position Sizing

### Model: Fixed Fractional with Equity Base

```
margin_per_trade = current_equity × sizing_pct
notional = margin_per_trade × leverage
```

- `sizing_pct` = 20% of equity per trade (adjustable via dashboard slider)
- `leverage` = 20x default (isolated margin)
- Maximum notional per trade: $200 (hard cap to prevent oversized positions)

**Example with $10 initial balance:**
| Trade | Equity | Sizing | Margin | Notional (20x) |
|-------|--------|--------|--------|----------------|
| 1st | $10.00 | 20% | $2.00 | $40.00 |
| After -5% loss | $9.90 | 20% | $1.98 | $39.60 |
| After +2% win | $10.30 | 20% | $2.06 | $41.20 |

**Minimum margin enforcement:**
```
min_margin_usd = initial_balance × min_margin_pct  # e.g., $10 × 15% = $1.50
if balance < min_margin_usd:
    skip new trades (wait for existing trades to close)
```

This prevents opening tiny positions that can't cover fees.

## Stop Loss & Take Profit

### Fixed TP/SL Model

| Parameter | Default | Dashboard Range |
|-----------|---------|----------------|
| Take Profit | 1.0% | 0.1% - 5.0% |
| Stop Loss | 0.5% | 0.1% - 5.0% |

**Risk-Reward Ratio:** 1.0% / 0.5% = **2:1 R:R**

### Trailing Stop

```
Activation: PnL% ≥ trailing_activation_pct (0.60%)
Trail distance: trailing_stop_pct (0.25%)
Exit level: highest_pnl_pct - trailing_stop_pct

Example:
  Entry → price rises to +0.60% → trailing ACTIVE
  Price rises to +1.30% → trail level = 1.30% - 0.25% = 1.05%
  Price drops to +1.04% → TRAILING_STOP at +1.05% (locks in > TP level)
```

**Critical rule:** Trailing stop only exits if the trail level is **at or above TP level**. This prevents trailing stop from exiting below the fixed TP, which would be worse than just waiting for TP.

```
if trail_exit_level >= take_profit_pct:
    if unrealized_pnl_pct < trail_exit_level:
        return "TRAILING_STOP"  # Exit — we've locked in >= TP
# Otherwise, fall through to fixed TP check
```

### Exit Priority

```
1. SL_HIT (always checked first — capital preservation)
2. TRAILING_STOP (only if trail level ≥ TP)
3. TP_HIT
4. MAX_HOLD (900 seconds = 15 minutes)
```

## Drawdown Protection

### Per-Session Loss Limit

```
daily_loss_limit_pct = 80%  # Stop trading if drawdown exceeds 80%
if (initial_balance - balance) / initial_balance > daily_loss_limit_pct:
    STOP_ALL_TRADING
```

With $10 initial balance, trading stops if balance drops below $2.00.

### Maximum Positions

```
max_positions = 5  # Default, adjustable 1-20 via slider
```

With 20% sizing and 5 max positions, the theoretical maximum exposure is:
- 5 positions × 20% equity × 20x leverage = **20× equity in notional**

At $10 equity: up to $200 total notional deployed.

### Cooldown Period

After closing a position on a symbol, a 15-second cooldown prevents immediately re-entering the same symbol. This avoids:
- Chasing the same move
- Whipsaw losses in choppy conditions
- Excessive round-trip fees on the same symbol

## Fee Impact Analysis

With $10 initial balance and 20x leverage:

| Trade Size | Round-trip Fee (0.10%) | Fee as % of Margin |
|-----------|----------------------|-------------------|
| $2 margin, $40 notional | $0.04 | 2.0% of margin |
| $2 margin, $40 notional | $0.04 | 2.0% of margin |

**Critical observation:** With 20x leverage, a 0.10% round-trip fee = **2% of margin**. This means:
- To break even on a trade, you need >0.10% gross price movement in your favor
- A 0.5% SL costs you 0.5% + 0.10% = 0.60% of notional = **12% of margin**
- A 1.0% TP earns you 1.0% - 0.10% = 0.90% of notional = **18% of margin**

**With leverage, fees are amplified relative to margin.** This is why realistic fee simulation is essential.

## Slider-Based Runtime Configuration

All risk parameters can be changed in real-time via the dashboard:

| Slider | Range | Affects New Positions | Affects Open Positions |
|--------|-------|----------------------|----------------------|
| TP% | 0.1 - 5.0% | ✅ | ✅ (immediate) |
| SL% | 0.1 - 5.0% | ✅ | ✅ (immediate) |
| Trailing% | 0.05 - 2.0% | ✅ | ✅ (immediate) |
| Trail Activation% | 0.1 - 5.0% | ✅ | ✅ (immediate, resets trailing) |
| Max Hold (sec) | 60 - 3600 | ✅ | ✅ (immediate) |
| Leverage | 1 - 125 | ✅ | ❌ (can't change mid-position) |
| Sizing% | 5 - 80% | ✅ | ❌ (position already sized) |
| Max Positions | 1 - 20 | ✅ | ❌ (doesn't close existing) |
| Min Margin% | 5 - 50% | ✅ | ❌ |

**Why this matters for backtesting:**
Every trade records a `runtime_config` JSON snapshot at open time. This captures the exact settings used, not the YAML config. So if you changed SL from 0.7% to 0.5% mid-session, the backtest knows which trades used 0.7% and which used 0.5%.

## Questions for Reviewers

1. **Is 2:1 R:R with 0.5% SL / 1.0% TP appropriate for meme-coin scalping?** Some scalpers use 1:1 R:R with higher win rates instead.
2. **Should position sizing be Kelly Criterion-based?** Currently it's fixed fractional. Kelly would adjust sizing based on recent win rate.
3. **Is 80% drawdown limit too loose?** At $10, you'd lose $8 before stopping. For a scalper, maybe 50% is more appropriate?
4. **Should trailing stop activation be tied to signal tier?** Tier 1 signals might warrant a wider trail than Tier 8.
5. **Is the 15-second cooldown too short?** In fast meme-coin markets, 15 seconds might not be enough to avoid re-entry into a failing trade.
