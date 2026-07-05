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
├── insight.md                         ← ⚡ START HERE — 11 targeted questions (Round 1)
├── insight_followup.md                ← Round 2: 13 follow-up questions (F1-F13), quantitative deep dive
├── insight_r3.md                      ← Round 3: 14 questions (R1-R14), implementation path + realism audit
├── insight_r4.md                      ← Round 4: 17 questions (S1-S17), foundation fixes + alternative strategy research
├── cross_analysis.md                  ← 🔥 Cross-analysis synthesis: 4-round findings, consensus, contradictions, decision framework
├── data/
│   └── PERFORMANCE_METRICS.md         ← Aggregate metrics, cost structure, breakeven tables
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

1. **🔥 Read `cross_analysis.md` first** — 4-round synthesis with consensus, contradictions, and decision framework
2. **⚡ Read `insight.md`** — 11 original targeted questions (Round 1)
3. Read `insight_followup.md` → `insight_r3.md` → `insight_r4.md` for the full progression
4. Read `poly-reference/ARCHITECTURE_POLY.md` to understand the profitable original
5. Read `docs/STRATEGY.md` for the current 8-tier signal logic
6. Compare with `poly-reference/momentum_poly.py` to see the simpler Fifteen approach
7. Check `docs/REALISTIC_EXECUTION.md` for execution cost analysis
8. Browse `snippets/` for implementation details
9. See `docs/OPEN_QUESTIONS.md` for broader known issues

## What We Want From You

- **Cross-validate the 4-round findings** — are the conclusions in `cross_analysis.md` correct?
- **Answer S12-S17** in `insight_r4.md` — research alternative strategies (HFT scalping, swing trading, Fifteen-direct-translation, etc.)
- **Is meme-coin scalping on Binance USDM fundamentally viable at ANY scale?** Or should we pivot to a different strategy class entirely?
- **What specific strategy would you run on Binance USDM Futures with $10 and a $5 VPS?**
- What single change would have the highest impact on profitability?

## Review Progress

| Round | File | Questions | Status | Key Finding |
|-------|------|-----------|--------|-------------|
| R1 | `insight.md` | Q1-Q11 | ✅ Reviewed (Claude) | Cost/TP ratio is the #1 problem |
| R2 | `insight_followup.md` | F1-F13 | ✅ Reviewed (Claude) | EV = -0.21%, structurally negative |
| R3 | `insight_r3.md` | R1-R14 | ✅ Reviewed (Claude) | Simulation optimistic, sizing 2× full-Kelly |
| R4 | `insight_r4.md` | S1-S17 | 🔄 Pending (Claude) + seeking cross-validation (Kimi, ZAI, others) | Foundation fixes + alternative strategy research |
| Synthesis | `cross_analysis.md` | — | ✅ Created | 18 findings, 4 contradictions, go/no-go framework |
