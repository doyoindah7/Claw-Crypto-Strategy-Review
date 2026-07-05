# Insight Questions — Critical Analysis Request

> **Context**: We have a Binance USDM Futures paper trading bot (8-tier meme scalp strategy) that was ported from a profitable Polymarket bot (Paper Fifteen — simple EMA+ROC momentum). The Polymarket bot was profitable. The crypto bot struggles. We need your sharpest reasoning on **why** and **what to change**.

## Strategy Architecture

**Q1.** Our Polymarket bot uses 1 signal type (EMA+ROC). Our crypto bot uses 8 tiers (VolSpike+Momentum, RSI+Vol, Funding+Mom, NewListing, ConsecutiveCandles, HighVol+Mom, DailyTrend, VWAP+RSI). Tiers 1+4+5 generate 75% of signals; tiers 2,3,8 rarely fire. **Is the 8-tier system extracting more edge, or just adding negative-expectancy trades from weak tiers? What's the cost of keeping tiers 6-8?**

**Q2.** Tier 1 (VolSpike+Momentum) confidence formula: `0.55 + min(0.15, vol_ratio/20) + min(0.15, |momentum|/5)`. This means even a weak 2.0x volume spike + 0.08% momentum = 0.65 confidence, which passes the 0.54 threshold. **Is our confidence floor too low? Are we taking trades with no real edge?**

## Stop/TP Width — The Core Paradox

**Q3.** Polymarket bot: TP 8%, SL 7.6% (R:R ~1:1, wide stops). Crypto bot: TP 1.0%, SL 0.5% (R:R 2:1, tight stops). Observed: crypto bot win rate 35-45%, and SL exits at -0.6% to -0.8% (SL + fees). **With meme coin spread (12-25bps) + slippage + 10bps round-trip fee, is TP 1.0%/SL 0.5% even viable? Should we test Fifteen's wide-stop approach (TP 3-5%, SL 2-4%) on crypto?**

**Q4.** At TP 1.0% / SL 0.5% with 0.178% round-trip cost on meme coins: breakeven win rate = 45.2%. But our actual win rate is 35-45%. **Is the strategy fundamentally unprofitable at these parameters, or is the win rate depressed by specific failure modes that are fixable?**

## Execution Friction

**Q5.** We poll prices every 2 seconds. On fast meme coin dumps, price can move 0.5% in <1 second. Our 0.5% SL can get blown past by 2-3x between polls. **What's the estimated SL overshoot cost from 2s polling vs WebSocket? Is WebSocket a prerequisite for tight-stop scalping?**

**Q6.** Meme coin effective spread: 12.5bps (meme) to 25bps (new meme listing). This means entry cost alone is 6-12bps before slippage. On a TP target of 100bps (1.0%), spread eats 6-12% of the profit target. **Is there a minimum spread threshold below which scalping is mathematically unprofitable? Should we skip meme coins entirely and focus on majors?**

## Leverage & Fee Interaction

**Q7.** 20x leverage: round-trip fee = 0.10% of notional = 2.0% of margin. A 0.5% SL loss = 10% of margin, but with fees = 12% of margin. **At what leverage does fee drag become the dominant factor in PnL? Is there a sweet spot between leverage (amplifies gains) and fee impact (amplifies costs)?**

**Q8.** Fifteen had NO leverage. Profit came from 8%+ price moves. Crypto bot uses 20x leverage to profit from 1% moves. **Is the leverage compensating for a strategy that doesn't generate enough alpha without it? If the signal only has 0.5% edge, does any amount of leverage make it profitable after costs?**

## Signal Quality

**Q9.** Momentum threshold: 0.08% on 1m candles. A meme coin moving from $0.00001200 to $0.00001210 qualifies. **Is 0.08% momentum on 1m candles signal or noise? What's the minimum price move that predicts continuation vs mean-reversion on meme coins?**

**Q10.** ADX regime filter threshold: 15 (standard is 20-25). At ADX 15, we trade in markets many consider choppy. **Is ADX < 20 the reason we're taking losing trades in chop, or is the lower threshold justified because crypto trends start faster than traditional markets?**

## If You Could Change One Thing

**Q11.** Given all constraints (Binance USDM, $10 bankroll, meme coins, realistic execution): **what single parameter or architectural change would you expect to have the highest impact on profitability? Why?**
