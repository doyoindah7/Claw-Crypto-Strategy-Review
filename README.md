# Claw-Crypto Strategy & Architecture Review

> This repository contains **strategy analysis, architecture documentation, and code pseudocode** from a Binance USDM Futures scalping bot. It is designed to be shared with AI assistants and human reviewers for **critical feedback, insight, and improvement suggestions**.

## Purpose

This is NOT a runnable bot. It is a **review artifact** containing:

- Detailed architecture breakdowns and data flow diagrams
- Full strategy logic with signal tier hierarchy
- Realistic execution simulation model (spread, slippage, fees, partial fills)
- Pseudocode and code snippets for each component
- Known issues, tradeoffs, and open questions

**Goal:** Get honest feedback on whether this strategy and architecture makes sense, where the weaknesses are, and what improvements would have the highest impact.

## Repository Structure

```
├── README.md                          ← You are here
├── docs/
│   ├── ARCHITECTURE.md                ← System architecture, data flow, component diagram
│   ├── STRATEGY.md                    ← Signal generation logic, tier hierarchy, indicators
│   ├── REALISTIC_EXECUTION.md         ← Spread/slippage/fee/partial-fill simulation model
│   ├── RISK_MANAGEMENT.md             ← Position sizing, SL/TP, trailing stops, drawdown limits
│   └── OPEN_QUESTIONS.md              ← Known issues, tradeoffs, things we're unsure about
├── snippets/
│   ├── signal_generation.py           ← Pseudocode: 8-tier signal evaluation pipeline
│   ├── market_scoring.py              ← Pseudocode: Market opportunity scoring algorithm
│   ├── realistic_executor.py          ← Pseudocode: Order execution simulation
│   ├── position_management.py         ← Pseudocode: Position tracking, exit logic, trailing stops
│   └── trade_persistence.py           ← Pseudocode: SQLite trade storage with runtime config snapshots
└── diagrams/
    └── system_flow.mermaid            ← Mermaid diagram: Full system data flow
```

## Quick Summary

| Aspect | Details |
|--------|---------|
| **Market** | Binance USDM Futures (perpetual contracts) |
| **Strategy** | Meme-cap scalping with 8-tier signal priority |
| **Timeframe** | 1-minute klines (configurable; was 5m) |
| **Position Mode** | Isolated margin, 20x leverage default |
| **Entry** | Volume spike + momentum + regime filter (ADX) |
| **Exit** | Fixed TP/SL, trailing stop, max hold time |
| **Execution** | Realistic simulation: spread, slippage, partial fills, taker fees |
| **Risk** | Per-trade sizing (% of equity), max concurrent positions, cooldowns |
| **Capital** | $10 initial balance (micro-scalping) |
| **Current Status** | Realistic paper trading — if profitable here, proceed to live |

## How to Review

1. Start with `docs/ARCHITECTURE.md` for the big picture
2. Read `docs/STRATEGY.md` for signal logic — this is the core
3. Check `docs/REALISTIC_EXECUTION.md` for how we simulate real trading conditions
4. Browse `snippets/` for pseudocode of each component
5. See `docs/OPEN_QUESTIONS.md` for things we specifically want feedback on

## Key Design Decisions (and why we made them)

1. **Realistic paper trading before live** — We simulate spread, slippage, fees, and fill probability because naive paper trading gives false confidence
2. **8-tier signal hierarchy** — Strongest signals (volume + momentum) get priority; weaker signals (VWAP reversion) are last resort
3. **ADX regime filter** — Only trade in trending markets (ADX > 15); choppy markets destroy scalpers
4. **Runtime config snapshots** — Every trade records the exact slider settings at open time, so backtest accuracy isn't compromised by config drift
5. **Slider changes update open positions** — When you change SL/TP via dashboard, existing positions update immediately (like moving stop-limit orders on an exchange)

## What We Want From You

- Is the 8-tier signal system sensible, or are there too many tiers?
- Is the realistic execution model missing any real-world friction?
- Are the risk management parameters reasonable for $10 starting capital?
- Any architectural red flags or antipatterns?
- What would you change to improve win rate or reduce drawdown?
- Are there better indicators or signal combinations for meme-coin scalping?
