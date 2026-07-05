"""
Trade Persistence with Runtime Config Snapshots
=================================================
Pseudocode extracted from TradeDB

The critical insight: every trade must record the EXACT config
at open time, not the YAML config. Users change sliders mid-session.
"""

# ─── Database Schema (40 columns) ────────────────────────────

SCHEMA_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    -- Identity
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,               -- LONG / SHORT
    session_id TEXT NOT NULL,         -- Bot session identifier
    
    -- Prices & Size
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    mid_price_entry REAL DEFAULT 0,   -- Mid price BEFORE spread
    leverage INTEGER NOT NULL,
    margin_usd REAL NOT NULL,
    notional_usd REAL NOT NULL,
    
    -- PnL Decomposition
    pnl_usd REAL NOT NULL,            -- Net PnL in USD
    pnl_pct REAL NOT NULL,            -- Net PnL% (after fees)
    gross_pnl_pct REAL DEFAULT 0,     -- PnL% before fees
    fee_impact_pct REAL DEFAULT 0,    -- Fee impact on PnL%
    
    -- Trade Details
    hold_sec REAL NOT NULL,
    exit_reason TEXT NOT NULL,         -- TP_HIT, SL_HIT, TRAILING_STOP, MAX_HOLD
    confidence REAL NOT NULL,
    signal_reason TEXT NOT NULL,
    
    -- Indicators at Entry
    volume_ratio REAL DEFAULT 0,
    momentum_pct REAL DEFAULT 0,
    rsi REAL DEFAULT 50,
    adx REAL DEFAULT 0,
    funding_rate REAL DEFAULT 0,
    
    -- Signal Accuracy
    max_favorable_pct REAL DEFAULT 0,  -- Highest PnL% during hold
    max_adverse_pct REAL DEFAULT 0,    -- Lowest PnL% during hold
    tp_would_hit INTEGER DEFAULT 0,    -- Did price reach TP level?
    sl_would_hit INTEGER DEFAULT 0,    -- Did price reach SL level?
    price_updates INTEGER DEFAULT 0,   -- Number of price ticks
    
    -- Execution Costs
    fee_usd REAL DEFAULT 0,
    spread_cost_usd REAL DEFAULT 0,
    entry_slippage_bps REAL DEFAULT 0,
    exit_slippage_bps REAL DEFAULT 0,
    entry_fee_usd REAL DEFAULT 0,
    exit_fee_usd REAL DEFAULT 0,
    total_fees_usd REAL DEFAULT 0,
    fill_qty_ratio REAL DEFAULT 1.0,
    is_partial_fill INTEGER DEFAULT 0,
    
    -- Timestamps
    opened_at REAL NOT NULL,
    closed_at REAL NOT NULL,
    
    -- ★ RUNTIME CONFIG SNAPSHOT ★
    runtime_config TEXT DEFAULT '{}'   -- JSON: settings at trade open time
);
"""

# ─── Runtime Config Snapshot ──────────────────────────────────
# This is the KEY feature for accurate backtesting.
#
# Without this, a backtest would assume all trades used the
# YAML config settings, which is WRONG if the user changed
# sliders mid-session.
#
# Example runtime_config JSON:
# {
#     "take_profit_pct": 1.0,      # Was 0.7% at session start, changed to 1.0%
#     "stop_loss_pct": 0.5,        # Was 0.7% at session start, changed to 0.5%
#     "trailing_stop_pct": 0.25,
#     "trailing_activation_pct": 0.60,
#     "max_hold_sec": 900,
#     "leverage": 20,
#     "sizing_pct": 0.20,          # 20% of equity per trade
#     "min_margin_pct": 0.15,
#     "max_positions": 5,
#     "initial_balance": 10.0,     # Original starting balance
#     "balance_at_open": 9.50,     # Available balance when trade opened
#     "equity_at_open": 10.30      # Total equity (balance + deployed margin)
# }

def save_trade(trade_data):
    """Save a completed trade with runtime config snapshot."""
    
    # Ensure runtime_config is serialized as JSON string
    runtime_cfg = trade_data.get("runtime_config", "{}")
    if isinstance(runtime_cfg, dict):
        runtime_cfg = json.dumps(runtime_cfg)
    
    # INSERT all 40 columns
    db.execute("""
        INSERT INTO trades (
            symbol, side, entry_price, exit_price, leverage,
            margin_usd, notional_usd, pnl_usd, pnl_pct, hold_sec,
            exit_reason, confidence, signal_reason,
            volume_ratio, momentum_pct, rsi, adx, funding_rate,
            max_favorable_pct, max_adverse_pct,
            tp_would_hit, sl_would_hit, price_updates, fee_usd,
            opened_at, closed_at, session_id,
            mid_price_entry, spread_cost_usd,
            entry_slippage_bps, exit_slippage_bps,
            entry_fee_usd, exit_fee_usd, total_fees_usd,
            fill_qty_ratio, is_partial_fill,
            gross_pnl_pct, fee_impact_pct,
            runtime_config
        ) VALUES (?, ?, ?, ...39 more... ?)
    """, (
        trade_data["symbol"], trade_data["side"], ...,
        runtime_cfg  # Last parameter
    ))


# ─── Backtest Query Methods ───────────────────────────────────

def get_trades_for_backtest(session_id=None, start_time=None, end_time=None):
    """Get trades with parsed runtime config for backtest analysis.
    
    Returns trades with runtime_config_parsed field — a dict
    containing the actual settings used for each trade.
    """
    trades = query_trades(session_id, start_time, end_time)
    for trade in trades:
        if trade["runtime_config"]:
            trade["runtime_config_parsed"] = json.loads(trade["runtime_config"])
        else:
            trade["runtime_config_parsed"] = {}
    return trades


def get_runtime_config_summary(session_id=None):
    """Get unique runtime config groups with their trade counts.
    
    Example output:
    [
        {
            "config": {"sl": 0.5, "tp": 1.0, ...},
            "trade_count": 45,
            "wins": 20,
            "total_pnl": 0.34,
            "avg_pnl_pct": 0.12,
        },
        {
            "config": {"sl": 0.7, "tp": 0.8, ...},
            "trade_count": 12,
            "wins": 3,
            "total_pnl": -0.56,
            "avg_pnl_pct": -0.18,
        }
    ]
    
    This lets you compare performance across different config settings
    within the same session — A/B testing in production.
    """
    return db.execute("""
        SELECT 
            runtime_config,
            COUNT(*) as trade_count,
            SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
            COALESCE(SUM(pnl_usd), 0) as total_pnl,
            COALESCE(AVG(pnl_pct), 0) as avg_pnl_pct
        FROM trades
        GROUP BY runtime_config
        ORDER BY trade_count DESC
    """)


# ─── Migration System ─────────────────────────────────────────
# When adding new columns, old databases are auto-upgraded.

MIGRATIONS = [
    "ALTER TABLE trades ADD COLUMN mid_price_entry REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN spread_cost_usd REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN entry_slippage_bps REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN exit_slippage_bps REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN entry_fee_usd REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN exit_fee_usd REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN total_fees_usd REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN fill_qty_ratio REAL DEFAULT 1.0",
    "ALTER TABLE trades ADD COLUMN is_partial_fill INTEGER DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN gross_pnl_pct REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN fee_impact_pct REAL DEFAULT 0",
    "ALTER TABLE trades ADD COLUMN runtime_config TEXT DEFAULT '{}'",
]

def apply_migrations(cursor):
    """Auto-add missing columns to existing databases."""
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(trades)")}
    
    for sql in MIGRATIONS:
        col_name = sql.split("ADD COLUMN ")[1].split()[0]
        if col_name not in existing_cols:
            cursor.execute(sql)
            log.info(f"Migration applied: {col_name}")


# ─── Why This Matters ─────────────────────────────────────────
#
# Problem: User runs a paper trading session for 4 hours.
#   Hour 1: SL=0.7%, TP=0.8% → 15 trades, 3 wins, -$0.45
#   Hour 2: Changes SL to 0.5%, TP to 1.0% → 20 trades, 9 wins, +$0.30
#   Hour 3: Changes SL to 0.3%, TP to 1.5% → 10 trades, 2 wins, -$0.60
#   Hour 4: Reverts to SL=0.5%, TP=1.0% → 18 trades, 8 wins, +$0.25
#
# Without runtime_config:
#   Backtest would assume ALL 63 trades used YAML config (SL=0.7%, TP=0.8%)
#   → Completely wrong results
#
# With runtime_config:
#   Backtest can group trades by their actual settings:
#   - SL=0.7%,TP=0.8%: 15 trades, 20% win rate, -$0.45
#   - SL=0.5%,TP=1.0%: 38 trades, 44.7% win rate, +$0.55
#   - SL=0.3%,TP=1.5%: 10 trades, 20% win rate, -$0.60
#   → Accurate A/B comparison
#   → Can confidently choose SL=0.5%, TP=1.0% as the best config
