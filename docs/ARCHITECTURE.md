# Architecture

## System Overview

The bot operates as a single-process Python application with an embedded HTTP dashboard. It follows a **scan → evaluate → execute → monitor → record** cycle.

```
┌──────────────────────────────────────────────────────────────────┐
│                        MAIN LOOP (2s tick)                       │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐   │
│  │  Price Update│───▶│  Exit Check  │───▶│  Close Position   │   │
│  │  (all open)  │    │  (SL/TP/Trail│    │  (calc PnL+fees) │   │
│  └─────────────┘    └──────────────┘    └────────┬──────────┘   │
│                                                  │               │
│                                                  ▼               │
│                                          ┌──────────────┐       │
│                                          │   TradeDB     │       │
│                                          │  (SQLite)     │       │
│                                          └──────────────┘       │
│                                                                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐   │
│  │   Scanner    │───▶│   Strategy    │───▶│  Realistic Exec  │   │
│  │  (every 5m)  │    │  (8 tiers)   │    │  (spread/slip/fee)│   │
│  └─────────────┘    └──────────────┘    └────────┬──────────┘   │
│                                                  │               │
│                                                  ▼               │
│                                          ┌──────────────┐       │
│                                          │  Open Position│       │
│                                          │  (PaperPosition)│     │
│                                          └──────────────┘       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │               HTTP Dashboard (port 8082)                     │ │
│  │  Live positions, trade history, equity curve, config sliders │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. BinanceFuturesClient (`binance_futures.py`)

**Responsibility:** Thin API wrapper with rate limiting and retry logic.

- Rate limit: 50ms minimum between requests (~20 req/sec)
- Monitors `X-MBX-USED-WEIGHT-1M` header; warns at >2000
- Retry on 429: reads `Retry-After` header
- Exchange info cached with 5-minute TTL
- Leverage tier mapping: BTC=125x, ETH=100x, majors=75x, meme=50x, default=20x

**Key methods:**
| Method | Endpoint | Weight |
|--------|----------|--------|
| `get_klines()` | `/fapi/v1/klines` | 5 |
| `get_price()` | `/fapi/v1/ticker/price` | 2 |
| `get_24h_tickers()` | `/fapi/v1/ticker/24hr` | 40 |
| `get_funding_rate()` | `/fapi/v1/fundingRate` | 1 |

### 2. MarketScanner (`market_scanner.py`)

**Responsibility:** Rank all Binance USDM perpetual markets by opportunity score. Runs every 5 minutes.

**Scoring formula:**
```
total_score = volume_score(0-30) + volatility_score(0-30) + new_listing_score(0-50)
```

| Component | Formula | Example |
|-----------|---------|---------|
| Volume | `min(30, max(0, 5 + 5 × log10(vol / 5M)))` | $5M→5, $50M→15, $500M→30 |
| Volatility | `min(30, max(0, |price_change_24h| × 2))` | 2%→4, 10%→20, 15%→30 |
| New Listing | Decaying bonus based on listing age | ≤1d→50, ≤3d→40, ≤7d→25, ≤14d→10 |

**Filters:** Minimum $5M 24h volume, minimum 2% 24h price change (new listings exempted).

**Output:** Top 30 markets sorted by `total_score` descending.

### 3. MemeScalpStrategy (`meme_scalp.py`)

**Responsibility:** Given a symbol, decide whether to generate a trading signal.

**Core pipeline:** Fetch klines → Calculate indicators → Apply regime filter → Evaluate 8 signal tiers → Emit or skip.

See [STRATEGY.md](STRATEGY.md) for full details.

### 4. RealisticPaperExecutor (`realistic_executor.py`)

**Responsibility:** Simulate realistic order execution to bridge the gap between naive paper trading and live trading.

See [REALISTIC_EXECUTION.md](REALISTIC_EXECUTION.md) for full details.

### 5. Bot Orchestrator (`bot_realistic_v2.py`)

**Responsibility:** Main loop, position management, trade recording, dashboard.

**Main loop (2-second tick):**
```
while running:
    1. Update prices for all open positions
    2. Check exit conditions (SL > TP > Trailing > Max Hold)
    3. Close positions that need closing (with realistic exit execution)
    4. Every 5 minutes: scan markets → evaluate strategy → open new positions
    5. Record trades to SQLite with runtime config snapshot
```

**Position lifecycle:**
```
Signal Generated
    → RealisticPaperExecutor.simulate_entry()
    → If filled: create PaperPosition (stores fill price, spread, slippage, fees)
    → Every 2s: update_price() → check should_exit()
    → If SL_HIT/TP_HIT: close at exact trigger price (stop-limit simulation)
    → If MAX_HOLD/TRAILING_STOP: close with simulate_exit() (market order simulation)
    → Record TradeRecord to in-memory list + SQLite
```

**Critical design choice — SL/TP exit price:**
- SL_HIT and TP_HIT use **exact trigger price** (simulating stop-limit orders on exchange)
- No spread or slippage on these exits — this is how exchange stop-limit works
- Only MAX_HOLD and TRAILING_STOP get spread + slippage (they're market orders)
- **But:** fees are still charged on exit (taker fee on close)
- **Net PnL = Gross PnL - Entry Fee - Exit Fee**

This means: SL at 0.5% → gross loss = 0.5% → net loss = 0.5% + 0.10% (round-trip fees) = **0.60%**

### 6. TradeDB (`trade_db.py`)

**Responsibility:** Persist trade history with runtime config snapshots for accurate backtesting.

**Key schema:** `trades` table with 40 columns including:
- Standard: symbol, side, prices, PnL, leverage, etc.
- Realistic execution: mid_price_entry, spread_cost, entry/exit slippage, entry/exit fees, fill ratio
- PnL decomposition: `gross_pnl_pct`, `fee_impact_pct`, `pnl_pct` (= gross - fee_impact)
- **`runtime_config`** (JSON): Snapshot of SL/TP/sizing/leverage/max_pos/initial_balance AT TRADE OPEN TIME

**Why runtime_config matters:**
The bot has a dashboard with live sliders. Users can change SL from 0.7% to 0.5% mid-session. Without `runtime_config`, a backtest would assume all trades used the YAML config's SL, not the actual SL when the trade was opened. This makes backtest results misleading.

**Migration system:** When the DB is opened, missing columns are auto-added via `ALTER TABLE`. Old trades get default values for new columns.

## Data Flow Diagram

```
Binance API
    │
    ├── get_klines(symbol, "5m", 60)  ──→  MemeScalpStrategy.evaluate()
    │                                         │
    │                                    ┌────┴────┐
    │                                    │ ADX < 15? │
    │                                    │ SKIP if   │
    │                                    │ not new   │
    │                                    └────┬────┘
    │                                         │ PASS
    │                                    8-tier evaluation
    │                                         │
    │                                    ScalpSignal?
    │                                    ┌────┴────┐
    │                                    │  YES     │ NO → skip
    │                                    └────┬────┘
    │                                         │
    ├── get_24h_tickers() ──→  Scanner ──→ for each top market:
    │                                         │
    │                              RealisticPaperExecutor.simulate_entry()
    │                              ┌──────────┴──────────┐
    │                              │ Fill? │ Reject? │ Partial?
    │                              └──┬──────────────────┘
    │                                 │ FILLED
    │                                 ▼
    │                          PaperPosition created
    │                                 │
    ├── get_price(symbol) ──→  update_price() every 2s
    │                                 │
    │                          should_exit()?
    │                          ┌───────┴───────┐
    │                          │ SL_HIT → close at trigger price
    │                          │ TP_HIT → close at trigger price
    │                          │ TRAILING_STOP → close with simulate_exit()
    │                          │ MAX_HOLD → close with simulate_exit()
    │                          └───────┬───────┘
    │                                  │
    │                                  ▼
    │                          TradeRecord → SQLite
    │                          (includes runtime_config JSON)
    │                                  │
    └──────────────────────────────────┘
```

## Threading Model

```
Main Thread                    HTTP Server Thread
┌──────────────────┐          ┌──────────────────┐
│  Bot main loop   │◄────────►│  Dashboard API   │
│  (2s tick)       │  shared  │  (GET /status)    │
│                  │  state   │  (POST /config)   │
└──────────────────┘          └──────────────────┘
```

- Single main thread runs the bot loop
- HTTP server runs in a daemon thread
- State is shared via `self.state` (no locks — potential race condition on config updates, but acceptable for a paper trading bot)
- Dashboard reads are non-blocking; config writes update `self._runtime_*` variables and existing open positions

## Known Architectural Limitations

1. **No lock on shared state** — Dashboard config updates can race with the main loop. In practice, this causes at most one trade to use a slightly stale config value.
2. **Single-process** — Cannot scale beyond what one machine can handle. Fine for current scope (<30 symbols, 2s polling).
3. **Polling-based** — Price updates every 2 seconds, not WebSocket. Can miss fast price moves between ticks.
4. **No order book depth** — Spread is simulated, not read from actual order book.
5. **In-memory positions** — Open positions are lost on crash (closed trades are persisted to SQLite).
6. **No reconnect logic** — If Binance API goes down, the bot retries per-request but has no exponential backoff or circuit breaker.
