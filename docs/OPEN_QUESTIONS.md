# Open Questions & Known Issues

## Strategy Questions

### 1. Too Many Signal Tiers?
We have 8 tiers. In practice, Tier 1 (Vol+Momentum) generates ~40% of signals, and Tiers 1+4+5 generate ~75%. The bottom 3 tiers (RSI, Funding, VWAP) rarely fire.

**Question:** Should we cut to 4-5 tiers and focus on what works? Or do the rare tiers add diversification value?

### 2. Momentum Threshold Sensitivity
With `momentum_threshold=0.08%` on 5m candles, a price moving from $0.00001200 to $0.00001210 would qualify. That's barely above noise level.

**Question:** Is 0.08% too sensitive? Should we require at least 0.15% (the code default)?

### 3. RSI Implementation
We use simple average RSI, not Wilder's EMA-based RSI. Simple average is more reactive but also more noisy.

**Question:** Does this matter for our use case? We only use RSI in Tier 2 (rare) and as a filter in Tier 8 (very rare).

### 4. ADX Threshold
We use ADX > 15 as "trending." Standard technical analysis uses 20-25. At 15, we're trading in markets that many analysts would consider choppy.

**Question:** Is the lower threshold justified for crypto where trends start earlier? Or are we taking bad trades in chop?

## Execution Questions

### 5. Slippage Model Too Tame?
Gaussian(1.5, 1.0) bps capped at 5 bps. In reality:
- Meme coins during volatility spikes: 10-50 bps slippage
- New listings: 20-100 bps
- Market orders during flash crashes: unlimited

**Question:** Should we use a fat-tailed distribution (e.g., log-normal or Pareto) for slippage? Or correlate slippage with volume_ratio (higher volume = more slippage)?

### 6. Stop-Limit vs Stop-Market for SL
We assume stop-limit orders for SL (exact trigger price, no slippage). But:
- Binance stop-limit can fail to fill if price gaps through
- Stop-market orders guarantee fill but have slippage

**Question:** Should we model stop-market as default? Or make it configurable?

### 7. Spread Is Static
We use fixed spread: 5 bps base, 2.5× for meme, 2.0× for new listings. Real spreads vary by:
- Time of day (wider during Asian night)
- Volatility (wider during dumps)
- Order book depth (wider for thin books)

**Question:** Should we fetch real bid-ask spread from the API instead of simulating?

## Architecture Questions

### 8. Polling vs WebSocket
We poll prices every 2 seconds. WebSocket would give sub-second updates and reduce API weight.

**Question:** Is 2-second polling adequate for a 0.5% SL? In a fast market, price can move 0.5% in <1 second on meme coins. Are we taking bigger SL hits than necessary due to polling latency?

### 9. No Order Book Data
We simulate spread instead of reading the actual order book. This means we can't detect:
- Thin liquidity (which causes larger real slippage)
- Spoofing (fake walls that disappear)
- Order book imbalances (predictive of short-term moves)

**Question:** Would adding L2 order book data significantly improve execution quality or signal quality?

### 10. Single-Timeframe Analysis
We only use 5m klines. No multi-timeframe analysis (e.g., 1m for entry timing, 15m for trend, 1h for context).

**Question:** Would multi-timeframe confluence filtering improve signal quality? E.g., only take long signals when 15m trend is also up?

## Risk Management Questions

### 11. Fixed Fractional vs Kelly
We use 20% of equity per trade regardless of win rate or signal confidence. Kelly Criterion would size positions based on estimated edge.

**Question:** Is fixed fractional adequate, or would Kelly-based sizing improve returns?

### 12. No Correlation Between Positions
We allow up to 5 concurrent positions, but they can all be LONG on correlated meme coins (e.g., PEPE + FLOKI + BONK all long). A single market dump would hit all 5 positions simultaneously.

**Question:** Should we limit correlated exposure? E.g., max 2 LONG meme positions at once, or max total notional in meme coins?

### 13. No Adaptive Parameters
All parameters are fixed or manually adjusted via sliders. No automatic parameter adjustment based on:
- Recent performance (reduce size after losses)
- Market regime (wider stops in high-vol periods)
- Time of day (different params for different sessions)

**Question:** Should we implement any adaptive parameter logic? Or keep it simple?

## Known Bugs / Technical Debt

### 14. Race Condition on Config Updates
Dashboard slider changes update `self._runtime_*` variables and open positions without locking. The main loop could read a half-updated state.

**Impact:** Low — at worst, one trade uses a slightly stale config value.

### 15. No Crash Recovery for Open Positions
Open positions are held in memory. If the bot crashes, open positions are lost. Only closed trades are persisted to SQLite.

**Impact:** Medium — a crash during a losing position means we avoid the loss, which makes backtest results unreliable.

### 16. No Reconnect Logic
If Binance API goes down, individual requests retry 3 times with linear backoff. No circuit breaker or exponential backoff.

**Impact:** Low — Binance API uptime is generally high, and 3 retries usually suffice.

### 17. PnL% Calculation Uses Simple Percentage
```
pnl_pct = (exit_price - entry_price) / entry_price * 100
```
This doesn't account for the compounding effect of reinvested profits. For a $10 account, this is fine. For larger accounts, this could misrepresent returns.

**Impact:** Negligible at current scale.

## Performance Observations

### 18. Typical Session Results (realistic paper mode)
- Win rate: 35-45%
- Average win: +0.7% to +1.2% (net)
- Average loss: -0.5% to -0.8% (net)
- Expectancy: slightly positive to breakeven
- Most profitable: Tier 1 signals on established meme coins
- Most damaging: Tier 4 (new listing) signals with high slippage

### 19. The SL Problem
Observed SL exits at 0.72%, 0.82%, 1.60% when config SL was 0.5%. Root cause:
- Fee impact: SL 0.5% + 0.10% round-trip fees = 0.60% net loss
- Stale config: Positions opened when SL was 0.7% still used old SL until we fixed this
- **Fix applied:** Slider changes now update existing open positions

### 20. Meme Coin Spread Is a Profit Killer
A new meme listing with 25 bps effective spread costs 0.125% per side. Combined with slippage and fees, the round-trip cost can exceed 0.35%. That means you need >0.35% gross profit just to break even on a trade.

**Implication:** Meme coins with wide spreads need wider TP targets (1.5-2.0%) to be consistently profitable.
