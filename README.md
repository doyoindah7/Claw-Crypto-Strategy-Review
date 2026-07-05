# Claw-Crypto Strategy & Architecture Review

> This repository contains **strategy analysis, architecture documentation, and code pseudocode** from a Binance USDM Futures scalping bot that was ported from a **profitable Polymarket bot (Paper Fifteen / PolyClaw-Cipher v3)**. It is designed to be shared with AI assistants and human reviewers for **critical feedback, insight, and improvement suggestions**.

## Purpose

This is NOT a runnable bot. It is a **review artifact** containing:

- Detailed architecture breakdowns and data flow diagrams
- Full strategy logic with signal tier hierarchy
- Realistic execution simulation model (spread, slippage, fees, partial fills)
- **Comparison with the profitable Polymarket bot** (Paper Fifteen) it was ported from
- Pseudocode and code snippets for each component
- Known issues, tradeoffs, and open questions

**Core Question:** The Polymarket bot was profitable. The crypto bot struggles. **Why? What should change?**

## Repository Structure

```
├── README.md                          ← You are here
├── insight.md                         ← ⚡ START HERE — 11 targeted questions for reviewers
├── docs/
│   ├── ARCHITECTURE.md                ← Crypto bot architecture, data flow, component diagram
│   ├── STRATEGY.md                    ← Signal generation logic, 8-tier hierarchy, indicators
│   ├── REALISTIC_EXECUTION.md         ← Spread/slippage/fee/partial-fill simulation model
│   ├── RISK_MANAGEMENT.md             ← Position sizing, SL/TP, trailing stops, drawdown limits
│   └── OPEN_QUESTIONS.md              ← Known issues, tradeoffs, things we're unsure about
├── poly-reference/
│   ├── ARCHITECTURE_POLY.md           ← Polymarket bot architecture + comparison table
│   └── momentum_poly.py               ← Original Fifteen strategy pseudocode + parameter diffs
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
| **Origin** | Ported from profitable PolyClaw-Cipher v3 (Polymarket bot) |
| **Current Status** | Realistic paper trading — if profitable here, proceed to live |

## The Key Comparison

| Parameter | Paper Fifteen (PM) | Crypto Bot (Binance) | Impact |
|-----------|-------------------|---------------------|--------|
| Signal types | 1 (EMA+ROC) | 8 tiers | Simple vs Complex |
| Min momentum | 0.002% | 0.08% | Ultra-sensitive vs Medium |
| TP / SL | 8% / 7.6% | 1.0% / 0.5% | Wide stops vs Tight stops |
| Round-trip cost | 25bps (no spread) | 22-35bps (fee + spread) | Similar total, different structure |
| Leverage | None | 20x | Fee amplification |
| Price feed | WebSocket (sub-ms) | REST polling (2s) | SL overshoot risk |
| Win rate | ~40% | 35-45% | Similar |
| Avg win | ~8% (net ~7.75%) | ~0.8% (net ~0.7%) | Much smaller per trade |
| **Result** | **Profitable** | **Struggling** | **Why?** |

## How to Review

1. **⚡ Read `insight.md` first** — 11 targeted questions that need your sharpest reasoning
2. Read `poly-reference/ARCHITECTURE_POLY.md` to understand the profitable original
3. Read `docs/STRATEGY.md` for the current 8-tier signal logic
4. Compare with `poly-reference/momentum_poly.py` to see the simpler Fifteen approach
5. Check `docs/REALISTIC_EXECUTION.md` for execution cost analysis
6. Browse `snippets/` for implementation details
7. See `docs/OPEN_QUESTIONS.md` for broader known issues

## What We Want From You

- **Why is the simple Fifteen strategy profitable while our complex 8-tier system struggles?**
- Should we simplify back to Fifteen's approach (1 signal type, wide stops) on Binance?
- Are tight stops (0.5% SL) viable on meme coins with real spread costs?
- Is 20x leverage helping or hurting after fee impact?
- What single change would have the highest impact on profitability?
