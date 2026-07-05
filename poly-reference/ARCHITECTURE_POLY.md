# PolyClaw-Cipher v3 Architecture (Polymarket Bot)

> This document describes the architecture of the original Polymarket bot that the Binance crypto bot was ported from. The goal is to compare the two architectures and understand why the Polymarket bot was profitable while the crypto bot struggles.

## PolyClaw-Cipher v3 System Overview

PolyClaw-Cipher v3 was a **multi-strategy Polymarket trading bot** running 3 concurrent instances:

| Instance | Strategy | TP/SL | Leverage | Bankroll | Result |
|----------|----------|-------|----------|----------|--------|
| **Paper Fifteen** | EMA+ROC momentum | TP 8%, SL 7.6% | None (binary) | $5 | Profitable |
| **Cipher v3** | Multi-strategy (momentum + mean-reversion + spread) | Variable | None | $5 | Break-even |
| **Scalper** | Convergence scalping | Tight | None | $5 | Marginal |

### Architecture: Async Event-Driven Pipeline

```
WebSocket (CLOB)
    |
    v
Feed Adapter (normalizes to Tick)
    |
    v
Event Bus (async pub/sub)
    |
    +---> Strategy Engine (evaluate all strategies on each tick)
    |         |
    |         v
    |     Signal(side, size, confidence)
    |         |
    +---> Risk Manager (filter + size)
    |         |
    |         v
    |     Approved Order
    |         |
    +---> Executor (FOK order via CLOB)
    |         |
    |         v
    |     Fill / Rejection
    |         |
    +---> State (SQLite WAL) --> Dashboard (FastAPI + WebSocket)
```

### Key Architectural Differences

| Aspect | PolyClaw-Cipher v3 | Binance Meme Scalp Bot |
|--------|-------------------|----------------------|
| **Runtime** | Async (asyncio) | Synchronous (threading) |
| **Price Feed** | WebSocket (sub-ms) | REST polling (2s interval) |
| **Event Model** | Event bus (pub/sub) | Direct function calls |
| **Order Type** | FOK (Fill-or-Kill) | Market order simulation |
| **Execution** | CLOB with real order book | Simulated spread + slippage |
| **State** | SQLite WAL + crash recovery | In-memory positions + SQLite trades |
| **Dashboard** | FastAPI + WebSocket push | HTTP polling (GET /status) |
| **Config** | YAML only (static) | YAML + live sliders (runtime) |
| **Strategies** | 3 strategies, 1 per instance | 1 strategy, 8 tiers |
| **Risk** | Dedicated RiskManager class | Inline in bot loop |
| **Sizing** | Kelly + fixed-fractional + ATR | Fixed-fractional only |

### What Made Fifteen Profitable

1. **Simple signal**: Only EMA+ROC, no confusion from multiple tiers
2. **Wide stops**: SL 7.6% gives trades room to breathe through noise
3. **No spread cost**: Polymarket CLOB fills at limit price, no bid-ask gap
4. **No leverage amplification of fees**: Fees are 25bps flat, not multiplied by 20x
5. **Sub-second price updates**: WebSocket means SL/TP triggers almost instantly
6. **FOK execution**: No partial fills, no ambiguity

### What Makes Crypto Bot Struggle

1. **8 signal tiers dilute edge**: Weaker tiers (5-8) add negative-expectancy trades
2. **Tight stops get stopped out by noise**: 0.5% SL on meme coins = constant SL hits
3. **Spread is a hidden tax**: 12-25bps per side on meme coins eats tight TP targets
4. **20x leverage amplifies fees**: 0.10% round-trip fee = 2% of margin at 20x
5. **2-second polling misses moves**: Fast dump can blow past 0.5% SL between polls
6. **Partial fills complicate exits**: 8% chance of partial fill = position size mismatch

### Paper Fifteen Analysis (from earlier research)

> "Analyzed paper fifteen bot simulation: conservative bias for Hyperliquid (slippage 40bps vs real 1-2bps, 25% trade rejection, 50x slower latency, phantom gas). Conclusion: **80-90% paper fifteen performance achievable on Hyperliquid from Tokyo.**"

This means: if we port Fifteen's simple momentum to Binance with realistic parameters, we should capture ~80-90% of its performance. The question is: what parameters?

## Migration Map (PolyClaw → Claw-Crypto)

| Polymarket Component | Crypto Equivalent | Status |
|---------------------|-------------------|--------|
| CLOB WebSocket | Binance REST API | Degraded (polling vs push) |
| EMA+ROC momentum | 8-tier signal system | Overcomplicated? |
| RiskManager class | Inline checks | Lost modularity |
| Kelly/ATR sizer | Fixed-fractional | Lost adaptivity |
| FOK execution | Simulated market orders | Added slippage |
| SQLite WAL + snapshots | SQLite trades only | Lost crash recovery |
| Event bus | Direct calls | Lost decoupling |
| Multi-strategy concurrent | Single strategy | Lost diversification |

## The Fundamental Question

The Polymarket bot was **simple**: one signal type, wide stops, no leverage, no spread. The crypto bot is **complex**: eight signal tiers, tight stops, 20x leverage, real spread costs.

**Did we add complexity that hurts rather than helps?**
