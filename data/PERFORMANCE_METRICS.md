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
| Expectancy | Slightly positive to breakeven | Borderline unprofitable |
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
