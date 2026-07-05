# Cross-Analysis: 4-Round AI Review Synthesis

> **Purpose**: This document synthesizes findings from all 4 rounds of AI strategy review (Claude), cross-references against the original strategy docs, identifies consensus points, unresolved contradictions, and produces an actionable decision framework. It is designed to be consumed by any AI reviewer (Claude, Kimi, ZAI, or others) for cross-validation.

---

## 1. Finding Consensus Matrix

Every major finding across R1–R4, tagged by which round identified or confirmed it:

| # | Finding | R1 | R2 | R3 | R4 | Consensus Strength |
|---|---------|:--:|:--:|:--:|:--:|-------------------|
| F1 | Cost/TP ratio is the #1 structural problem (17.8% vs Fifteen's 3.1%) | **ID** | ✓ | ✓ | ✓ | **STRONG — unanimous** |
| F2 | TP 1.0%/SL 0.5% is too tight for meme coin spread + slippage | **ID** | ✓ | ✓ | ✓ | **STRONG — unanimous** |
| F3 | EV is structurally negative (-0.21% per trade) | | **ID** | ✓ | ✓ | **STRONG — confirmed with math** |
| F4 | Leverage does NOT create edge; it amplifies costs proportionally | **ID** | ✓ | ✓ | ✓ | **STRONG — unanimous** |
| F5 | Additive confidence formula allows weak signals to pass | **ID** | ✓ | ✓ | ✓ | **STRONG — unanimous** |
| F6 | Multiplicative (AND-gate) confidence is needed | | **ID** | ✓ | ✓ | **STRONG — design agreed** |
| F7 | Simulation is systematically optimistic | | | **ID** | ✓ | **STRONG — detailed audit** |
| F8 | Slippage model (Gaussian cap 5bps) is far too tame | | | **ID** | ✓ | **STRONG — unanimous** |
| F9 | SL exits should have 1.5× worse slippage (adverse selection) | | | **ID** | ✓ | **STRONG — unanimous** |
| F10 | Position sizing at N=5 e=20% L=8 is 2× full-Kelly | | | **ID** | ✓ | **STRONG — confirmed with math** |
| F11 | Replay pipeline is the #1 priority before any parameter changes | | | **ID** | ✓ | **STRONG — unanimous** |
| F12 | 8 tiers may be diluting edge — weak tiers add negative-EV trades | **ID** | ✓ | | | **MODERATE — identified but not quantified** |
| F13 | Wide stops (TP 3%/SL 2%) could fix cost/TP ratio | | **ID** | ✓ | ✓ | **MODERATE — needs validation** |
| F14 | WR may drop when widening stops (WR-vs-TP elasticity unknown) | | **ID** | ✓ | ✓ | **MODERATE — unvalidated** |
| F15 | $10 bankroll cannot generate meaningful profit even with correct params | | **ID** | ✓ | ✓ | **STRONG — confirmed** |
| F16 | Stop-market on exchange (mark price) eliminates SL overshoot | | | **ID** | ✓ | **STRONG — confirmed** |
| F17 | Binance USDM has no native OCO for futures | | | | **ID** | **CONFIRMED — architectural constraint** |
| F18 | 5 concurrent correlated meme positions = one joint bet | | | **ID** | ✓ | **STRONG — risk model consensus** |

**Legend**: **ID** = first identified, ✓ = confirmed/referenced

---

## 2. Unresolved Contradictions & Open Debates

### 2.1 WR Elasticity: Does Widening Stops Kill Win Rate?

| Position | Argument | Source |
|----------|----------|--------|
| Optimistic | Wider stops survive noise → WR should increase or hold | R2 Claude (F2) |
| Pessimistic | Wider TP means price must travel further → WR likely drops 5-10% | R2 Claude (F2, conservative estimate) |
| Neutral | Only replay can answer this — we have no data | R3 Claude (R1-R3) |

**Current status**: UNRESOLVED — blocked on replay pipeline. This is the single most important empirical question. If WR at TP 3%/SL 2% is ≥44%, the strategy is viable after cost model fixes. If WR drops below 38%, the entire approach may be dead.

### 2.2 Kill Weak Tiers or Keep for Diversification?

| Position | Argument | Source |
|----------|----------|--------|
| Kill tiers 6-8 | They generate ~19% of signals but likely have negative EV | R1 Q1 |
| Keep all tiers | Diversification benefit — rare tiers might shine in specific regimes | Original design intent |
| Data needed | Per-tier WR is NOT tracked — can't decide without data | R3 (data gap) |

**Current status**: UNRESOLVED — blocked on per-tier WR data from replay. The bot's DB has `signal_reason` column which maps to tiers, so replay CAN produce this data.

### 2.3 Optimal Leverage at $10 Bankroll

| Position | Leverage | Argument | Source |
|----------|----------|----------|--------|
| Conservative | L=3 | N×e×L ≤ 2.0 with N=3, e=20% → survivable | R4 S7 |
| Moderate | L=8 | Claude's original proposal, half-Kelly at N=3 e=8.5% | R2 F13 |
| Aggressive | L=20 | Current, but 2× full-Kelly → ruin risk | R3 (proven too aggressive) |

**Current status**: PARTIALLY RESOLVED — L=20 is confirmed too aggressive. The choice between L=3 and L=8 depends on whether WR at wider stops justifies the larger notional per trade. At $10, L=3 with N=3 gives $6 notional per position (barely above $5 Binance minimum). L=8 with N=1 gives $20 (comfortable but only 1 position at a time).

### 2.4 Fix Simulation First or Switch Parameters First?

| Position | Approach | Risk | Source |
|----------|----------|------|--------|
| Fix sim first | Make simulation realistic → then measure → then decide | Loses comparability with ~200 existing trades | R3 R13 (Claude's recommendation) |
| Switch params first | Try TP 3%/SL 2% now under optimistic sim → if profitable even under optimistic, likely profitable for real | May get false positive from optimistic sim | Implicit alternative |
| Both in parallel | Fix sim + replay historical with new cost model + start fresh forward | Maximum data, but most engineering effort | R4 S1 (option c) |

**Current status**: RESOLVED — Claude recommends option (c): fix sim + replay historical + start fresh. This is the most rigorous path. The question is whether we have the engineering bandwidth.

---

## 3. The Causal Chain: Why Crypto Bot Struggles

This section traces the root cause from symptom to structural origin:

```
Symptom: Net PnL is negative
    │
    ▼
Direct cause: EV per trade = -0.21% (structurally negative)
    │
    ├──► Why? Cost/TP ratio = 17.8% (fees eat 17.8% of every TP target)
    │       │
    │       ├──► Why? TP = 1.0% (too small a target for the cost structure)
    │       │       │
    │       │       └──► Why so small? 1m/5m scalping targets tiny moves
    │       │
    │       ├──► Why? Spread = 12.5-25bps (meme coins have wide spreads)
    │       │       │
    │       │       └──► Why? Meme coins are illiquid relative to majors
    │       │
    │       └──► Why? Leverage 20x amplifies fee as % of margin
    │               │
    │               └──► Why 20x? $10 bankroll needs leverage for meaningful PnL
    │
    ├──► Why? Win rate 35-45% < breakeven 54.3% (using effective SL 0.8%)
    │       │
    │       ├──► Why? SL 0.5% gets hit by noise on meme coins
    │       │       │
    │       │       └──► Why? Meme coins have 2-5% ATR — 0.5% SL is 10-25% of typical range
    │       │
    │       ├──► Why? SL overshoot (actual -0.72% to -1.60% vs configured -0.5%)
    │       │       │
    │       │       └──► Why? 2s polling + no stop-market on exchange
    │       │
    │       └──► Why? Weak signals pass additive confidence formula
    │               │
    │               └──► Why? Formula designed to be permissive (more trades = more data)
    │
    └──► Why? Simulation is optimistic → EV -0.21% is an UPPER BOUND
            │
            ├──► Slippage capped at 5bps (real: 10-50+bps during volatility)
            ├──► SL exits have zero slippage (real: 1.5× worse than market)
            ├──► Static spread (real: widens during volatility)
            └──► Position PnL treated as independent (real: correlated meme dumps)
```

**Root cause summary**: The strategy was ported from a market (Polymarket CLOB) where spread is zero, execution is instant, and wide stops (8%) make cost negligible. On Binance USDM with meme coins, the cost structure is fundamentally different — and the port didn't adapt for it. The 8-tier complexity, tight stops, and high leverage are all symptoms of trying to force a wide-stop, low-cost strategy into a tight-stop, high-cost environment.

---

## 4. Quantitative Summary: Current vs Proposed

| Metric | Current (Measured) | Proposed (R2 Claude) | Proposed (R4 Conservative) | Notes |
|--------|--------------------|-----------------------|----------------------------|-------|
| TP | 1.0% | 3.0% | 3.0% | Same direction |
| SL | 0.5% | 2.0% | 2.0% | Same |
| Leverage | 20x | 8x | 3-8x | Range depends on N |
| Position size | 20% equity | 20% equity | 8.5-25% equity | Kelly-dependent |
| Max positions | 5 | 5 | 1-3 | Reduced for $10 |
| Confidence type | Additive | Multiplicative | Multiplicative | Same |
| Confidence threshold | 0.54 | 0.60 | 0.55-0.60 | Needs sweep |
| ADX | 15 | 18 | 15-18 | Minor |
| Momentum threshold | 0.08% fixed | max(0.03%, 0.04×ATR%) | ATR-adaptive | Same direction |
| Breakeven WR | 45.2% | 44.0% | 44.0% | At TP3/SL2 |
| Estimated actual WR | 35-45% | 38-45% | 38-45% | UNVALIDATED |
| EV per trade | -0.21% | +0.05% (if WR≥45%) | +0.05% | UNVALIDATED |
| Cost/TP ratio | 17.8% | 5.9% | 5.9% | 3× improvement |
| Kelly sizing factor | 8.0× (2× full-Kelly) | 2.0× (half-Kelly) | 1.8-2.0× (half-Kelly) | Same target |
| Slippage model | Gaussian cap 5bps | Mixture 80/20 | Mixture 80/20 | Same |
| SL exit slippage | Zero | 1.5× market | 1.5× market | Same |

---

## 5. Implementation Priority Stack

Ranked by: (a) unblocks other work, (b) reduces uncertainty, (c) requires no capital

| Priority | Task | Unblocks | Risk if Skipped | Status |
|----------|------|----------|-----------------|--------|
| **P0** | Build replay pipeline (1m klines) | WR elasticity, per-tier WR, MFE | All parameter decisions remain guesses | NOT STARTED |
| **P0** | Fix slippage model (mixture dist + SL 1.5×) | Trustworthy EV | Continuing to make decisions on inflated numbers | NOT STARTED |
| **P1** | Replay ~200 trades at TP3%/SL2% | Go/no-go on wide stops | May waste weeks on wrong parameters | BLOCKED on P0 |
| **P1** | Per-tier WR from replay | Tier cull decision | May keep negative-EV tiers | BLOCKED on P0 |
| **P2** | Implement multiplicative confidence | Signal quality filter | Weak signals continue passing | READY (design complete) |
| **P2** | Fix position sizing to half-Kelly | Capital survival | Ruin at current 2× full-Kelly | READY (formula defined) |
| **P3** | Stop-market on exchange (testnet) | Eliminate SL overshoot | SL overshoot continues | NEEDS CODE CHANGES |
| **P3** | Binance testnet validation | Trust in simulation | Paper mode may not match reality | NEEDS ACCOUNT SETUP |
| **P4** | Bayesian sequential testing framework | Future A/B testing | Classical tests need 773+ trades | DESIGN ONLY |
| **P4** | Dynamic spread fetching | Simulation realism | Spread underestimation | NICE-TO-HAVE |

---

## 6. Decision Framework: Go/No-Go Gates

```
START
  │
  ▼
[GATE 0] Build replay pipeline + fix slippage model
  │
  ├── FAIL: Can't build pipeline → paper trade with fixed sim, wait for 200+ new trades
  │
  ▼ PASS
  │
[GATE 1] Replay at TP3%/SL2% → WR ≥ 44%?
  │
  ├── NO: WR < 38% → STRATEGY IS DEAD at these params. PIVOT (see Section 7).
  ├── MAYBE: WR 38-44% → Marginal. Try TP5%/SL3%. If still <45% → PIVOT.
  │
  ▼ YES: WR ≥ 44%
  │
[GATE 2] Which tiers have positive EV?
  │
  ├── Only Tier 1: Drop tiers 2-8, run Tier 1 only
  ├── Tiers 1+2+4: Keep top 3, cull 5-8
  ├── All negative: Signal logic is broken → PIVOT
  │
  ▼ At least one tier positive
  │
[GATE 3] Implement: multiplicative confidence + half-Kelly sizing + stop-market
  │
  ▼
[GATE 4] Fresh paper trade for 200+ trades with new params
  │
  ├── WR < 44%: Re-exit simulation, go back to GATE 1
  │
  ▼ WR ≥ 44% consistently
  │
[GATE 5] Testnet live for 100+ trades
  │
  ├── Discrepancy > 20% vs paper: Fix simulation, return to GATE 0
  │
  ▼ Consistent
  │
GO LIVE (with $10 as validation capital, NOT profit capital)
```

---

## 7. Pivot Options (If Scalping Is Dead)

If replay confirms WR < 38% at TP3%/SL2%, the current 8-tier meme scalp approach is not viable on Binance USDM at $10. Options:

| # | Pivot Direction | Description | Expected Edge Source | Capital Needed | Difficulty |
|---|----------------|-------------|---------------------|----------------|------------|
| P1 | **Fifteen-style on majors** | EMA+ROC on BTC/ETH, TP 3-5%, SL 2-4%, no leverage or L=2-3 | Momentum continuation on liquid assets | $10 viable (no leverage needed for $5 min) | Low — we have the profitable reference |
| P2 | **Funding rate arbitrage** | Collect funding on positions with extreme rates | Structural positive carry from funding rate | $50+ (position must survive mark-price swings) | Medium |
| P3 | **Mean-reversion on majors** | RSI extreme + Bollinger band on 15m/1h, TP 1-2%, SL 1% | Reversion to mean on liquid assets with tight spreads | $10 with L=3-5 | Medium |
| P4 | **Multi-timeframe swing** | 1h trend + 15m entry, hold 4-24 hours, TP 5-15% | Capturing multi-hour trends | $10 with L=2-3 | Medium-High |
| P5 | **Market-making on liquid pairs** | Provide liquidity on BTC/ETH, capture spread | Bid-ask spread capture | $100+ (need inventory buffer) | Very High — needs WebSocket, fast execution |
| P6 | **Cross-exchange arbitrage** | Buy on Binance, sell on Bybit/OKX when price diverges | Temporary price discrepancy | $50+ per exchange | Very High — needs multi-exchange infra |

**Key insight**: P1 (Fifteen-style on majors) is the most natural pivot — it's literally what already worked on Polymarket, adapted to crypto majors where spread is 5bps (not 12.5-25bps). The cost/TP ratio at TP 5% on majors would be 0.178%/5% = 3.6% — comparable to Fifteen's 3.1%.

---

## 8. Questions for Cross-Validation by Other AIs

These are the questions where a second (or third) independent opinion would be most valuable:

### 8.1 Core Disagreement Zones

**CV1.** Claude says EV is -0.21% and likely worse. **Is this calculation correct?** The formula used was `EV = 0.4 × 0.95% - 0.6 × 0.65% - 0.2%`. Is the 0.95% avg win and 0.65% avg loss reasonable given the observed ranges (+0.7-1.2% win, -0.5-0.8% loss)?

**CV2.** Claude proposes TP 3%/SL 2% as the fix. **Is there a theoretical or empirical basis for this specific ratio?** Why not TP 5%/SL 3% or TP 2%/SL 1.5%? What determines the optimal TP/SL for a given cost structure?

**CV3.** The multiplicative confidence formula: `0.50 + 0.35 × (vol_score × mom_score)`. **Is 0.50 the right base?** At zero volume and zero momentum, confidence = 0.50 (coin flip). Should the base be lower (0.40?) to ensure the AND-gate actually filters?

**CV4.** Half-Kelly target: N×e×L ≤ 2.0. **Is this the correct constraint for correlated positions?** Claude treats N concurrent meme positions as one joint bet. But correlation isn't 1.0 — some meme pairs have ρ ≈ 0.6, others ρ ≈ 0.9. How should partial correlation be incorporated?

### 8.2 Strategic Questions

**CV5.** Is meme-coin scalping on Binance USDM fundamentally viable for ANY strategy at $10 bankroll? Or is the $5 Binance minimum notional + meme spread a structural barrier that no amount of parameter tuning can overcome?

**CV6.** The cost/TP ratio is identified as the #1 problem. But Polymarket's CLOB had 25bps total cost (fee only, no spread). Binance meme coins have 17.75-25.5bps (fee + spread). The costs are SIMILAR in absolute terms. **Is the real problem not cost, but that meme coins don't move 8% in 15 minutes like Polymarket contracts do?** In other words, is the issue that crypto TP targets are too small relative to the natural price movement range?

**CV7.** If we accept that $10 is a validation-only bankroll, what is the minimum viable sample size to confirm edge? Claude says 379 trades for ±5% CI. But if we're just checking "is WR > 44%", we need far fewer trades for directional confirmation. **What's the minimum sample for a binary hypothesis test (H0: WR ≤ 40%, H1: WR ≥ 45%) at 80% power?**

### 8.3 Alternative Strategy Validation

**CV8.** Pivot option P1 (Fifteen-style on majors): EMA+ROC with TP 5%/SL 4% on BTC/ETH perpetuals. **What's the estimated WR for this approach?** Majors have tighter spreads (5bps) but also lower volatility and more efficient markets. Is there enough momentum signal on majors for a simple EMA+ROC to have edge?

**CV9.** Pivot option P4 (multi-timeframe swing): 1h trend + 15m entry. **What indicators would you use?** Simple EMA crossover on 1h? Or would you need order flow, funding rate, or on-chain data for a genuine edge?

**CV10.** Is there a well-documented crypto scalping strategy with proven positive EV after realistic costs? **Not theoretical — actual live-traded, audited results.** We've seen many strategies that work in backtest but fail live. What's the track record of high-frequency scalping on Binance USDM specifically?

---

## 9. Data Availability for Cross-Validators

| Data | Available? | Location | Format |
|------|-----------|----------|--------|
| Aggregate WR, PnL | Yes | `data/PERFORMANCE_METRICS.md` | Summary tables |
| Strategy logic | Yes | `docs/STRATEGY.md` | Full 8-tier spec |
| Execution simulation | Yes | `docs/REALISTIC_EXECUTION.md` | Pipeline + params |
| Risk management | Yes | `docs/RISK_MANAGEMENT.md` | Sizing, stops, limits |
| Polymarket reference | Yes | `poly-reference/` | Architecture + code |
| Code snippets | Yes | `snippets/` | Pseudocode |
| Per-trade raw data | No | On bot server only | SQLite, 40+ columns |
| Per-tier WR | No | Not tracked | — |
| Order book data | No | Not captured | — |
| Tick-level price data | No | Not captured | — |

---

## 10. Meta-Observation: Review Process Itself

| Aspect | Assessment |
|--------|-----------|
| **Convergence** | 4 rounds of review have converged on the same core findings — this is a strong signal that the diagnosis is correct |
| **Diminishing returns** | Each additional round adds less new information. R1 identified the problem. R2 quantified it. R3 audited the measurement tool. R4 is mostly implementation details. |
| **Action gap** | We have 4 rounds of analysis but 0 rounds of implementation. The bottleneck is no longer understanding — it's building the replay pipeline and fixing the simulation. |
| **Key risk** | "Analysis paralysis" — continuing to review without building. The next step should be CODE, not more questions. |

---

## Appendix: Round-by-Round Summary

### Round 1 (`insight.md`) — Problem Identification
- 11 targeted questions covering strategy architecture, stop width, execution friction, leverage, and signal quality
- Core insight: cost/TP ratio is 17.8% vs Fifteen's 3.1%
- Questions remain open for reviewer response

### Round 2 (`insight_followup.md`) — Quantitative Deep Dive
- 13 follow-up questions (F1-F13) building on R1 answers
- Key calculations: EV = -0.21%, breakeven WR by TP/SL, ruin math
- Proposed parameter set: TP 3%, SL 2%, L=8, multiplicative confidence
- Minimum bankroll for profit: $1,000

### Round 3 (`insight_r3.md`) — Implementation Path + Realism Audit
- 14 questions (R1-R14) focused on HOW to implement fixes
- Critical finding: simulation is systematically optimistic
- EV -0.21% is an upper bound — real EV likely more negative
- Position sizing is 2× full-Kelly — way too aggressive
- R14: full simulation realism audit with rating for each component

### Round 4 (`insight_r4.md`) — Foundation Fixes + Side Quests
- 17 questions (S1-S17) on implementation specs + alternative strategy research
- Slippage mixture distribution design (S2-S4)
- Position sizing at $10 with $5 Binance minimum (S5-S7)
- Binance OCO / conditional order mechanics (S8-S9)
- Replay pipeline ambiguity handling (S10)
- Meta question: pivot to measurement-first approach? (S11)
- Side-quest: HFT scalping, swing trading, Fifteen translation, profitable bot lit review, strategy ranking, $10 viability (S12-S17)

### Cross-Validation Round (Claude R4 responses + Kimi/ZAI R1 integration)

**Key new findings:**

| Finding | Detail | Impact |
|---------|--------|--------|
| **Breakeven WR = 54.3%** (Claude recalculation) | Using EFFECTIVE SL 0.8% (observed), not configured SL 0.5%, and NOT adding overshoot as symmetric cost | Even higher than Kimi's 51.7% — strategy is MORE dead than anyone calculated |
| **Math error in S7** | Worst-case 3 SL hits = 3.6% bankroll (not 10.8% as we wrote — triple-counting error) | L=3/N=3/e=20% is actually safer than we thought |
| **Leverage "red herring" = same claim** | ZAI and Claude say the same thing in different words — fee/SL ratio invariant to leverage | No real disagreement |
| **No audited profitable crypto bot exists publicly** | Claude searched — landscape is marketing content only, no independent audit | Honest confirmation the field is barren |
| **Fifteen R:R >1.5:1 confirmed** | TP8/SL5 breakeven = 39.2% at 40% WR = marginal profit ✓ | Viable pivot direction |
| **WR at wide stops = GENUINELY UNRESOLVED** | Both directions valid logically, only empirical data resolves it | Replay pipeline is THE unblocker |
| **AND-gate + log-scale volume = compatible** | Replace linear vol_score with `min(1, log2(vol_ratio)*k)` in multiplicative formula | Combined best of Claude + ZAI proposals |

**Breakeven WR — The Critical Resolution:**

| Method | Breakeven WR | Who | Correct? |
|--------|-------------|------|----------|
| Config SL 0.5%, no overshoot | 45.2% | Claude R2, ZAI | Understates real SL impact |
| Config SL 0.5%, overshoot as symmetric cost | 51.7% | Kimi | Overshoot isn't symmetric (doesn't affect TP) |
| **Effective SL 0.8%, no symmetric overshoot** | **54.3%** | **Claude R4 recalc** | **Most accurate — uses observed SL exit** |

**Conclusion**: The true breakeven WR at current parameters is **54.3%**. Our actual WR is 35-45%. The gap is 9-19 percentage points. The strategy is not just negative EV — it's deeply, structurally negative.
