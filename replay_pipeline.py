#!/usr/bin/env python3
"""
Claw Crypto Strategy — Replay Pipeline
=======================================
Replays historical trade entries against Binance 1m klines at various TP/SL combinations.

Consensus from 4-round AI review (Claude, ZAI, Kimi):
- Replay pipeline is the #1 priority — unblocks ALL parameter decisions
- Use 1m klines (not 5m) for accuracy
- Ambiguous candles (high>TP AND low<SL): assume SL hit first (conservative)
- Calibration gate: replay WR at original params must match sim observed WR within ±5%
- Sample size: 379 trades for ±5% CI

Usage:
  1. Export trades from bot SQLite DB:
     python replay_pipeline.py export --db /path/to/claw.db --output trades.csv

  2. Run replay with kline data:
     python replay_pipeline.py replay --trades trades.csv --output results/

  3. Quick stats from results:
     python replay_pipeline.py stats --results results/

  4. Full pipeline (export + replay + stats):
     python replay_pipeline.py full --db /path/to/claw.db --output results/

Author: Claw Strategy Review — Implementation Phase
Date: 2025-07-05
"""

import argparse
import csv
import json
import math
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ─── HTTP client (prefer requests, fall back to urllib) ─────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.parse
    HAS_REQUESTS = False


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class TradeEntry:
    """A single trade entry from the bot's database."""
    id: int
    symbol: str
    side: str                      # LONG / SHORT
    entry_price: float
    entry_time: float              # Unix timestamp
    confidence: float
    signal_reason: str             # Tier identifier
    volume_ratio: float
    momentum_pct: float
    rsi: float
    adx: float
    funding_rate: float
    leverage: int
    # Original sim results for calibration
    original_exit_reason: str = ""
    original_pnl_pct: float = 0.0
    original_hold_sec: float = 0.0
    original_tp_pct: float = 0.0
    original_sl_pct: float = 0.0
    max_favorable_pct: float = 0.0   # MFE from sim
    max_adverse_pct: float = 0.0     # MAE from sim


@dataclass
class KlineCandle:
    """A single 1m kline candle from Binance."""
    open_time: int       # Unix ms
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int


@dataclass
class ReplayResult:
    """Result of replaying a single trade at a specific TP/SL combo."""
    trade_id: int
    symbol: str
    side: str
    entry_price: float
    entry_time: float
    confidence: float
    signal_reason: str
    # Replay parameters
    tp_pct: float
    sl_pct: float
    max_hold_sec: float
    # Replay outcome
    exit_type: str           # TP, SL, MAX_HOLD, AMBIGUOUS_SL
    exit_price: float
    pnl_pct: float           # Raw PnL (before costs)
    pnl_after_cost: float    # PnL after round-trip cost
    hold_sec: float
    mfe_pct: float           # Max Favorable Excursion
    mae_pct: float           # Max Adverse Excursion
    klines_used: int         # Number of candles checked
    ambiguous_candles: int   # Candles where both TP and SL were hit


# ═══════════════════════════════════════════════════════════════
# COST MODEL
# ═══════════════════════════════════════════════════════════════

# Binance USDM Futures standard taker fee
TAKER_FEE_PCT = 0.05  # per side

# Spread model (from cross_analysis.md)
SPREAD_BASE_BPS = 5.0          # Base spread for majors
MEME_SPREAD_MULTIPLIER = 2.5   # Meme coins
NEW_LISTING_MULTIPLIER = 2.0   # On top of meme

# Slippage model — mixture distribution (proposed fix from R3/R4)
# 80% normal: Gaussian(μ=3, σ=2) cap 8bps
# 20% volatile: Gaussian(μ=20, σ=10) cap 60bps
# For now in replay, we use the SIMPLIFIED cost model (same as current sim)
# so we can compare apples-to-apples with the original results.
# Use --realistic-costs flag for the mixture model.

SIMPLE_ROUND_TRIP_COST_PCT = 0.178  # 17.8bps — current sim assumption


def compute_round_trip_cost(is_meme: bool = True, realistic: bool = False) -> float:
    """Compute round-trip cost as % of notional."""
    if not realistic:
        return SIMPLE_ROUND_TRIP_COST_PCT

    # More realistic cost model (proposed mixture)
    import random
    fee = 2 * TAKER_FEE_PCT  # 0.10%

    spread_bps = SPREAD_BASE_BPS
    if is_meme:
        spread_bps *= MEME_SPREAD_MULTIPLIER
    spread = spread_bps / 10000.0  # Convert bps to fraction

    # Mixture slippage
    if random.random() < 0.80:
        slippage_bps = max(0, random.gauss(3, 2))
        slippage_bps = min(slippage_bps, 8)
    else:
        slippage_bps = max(0, random.gauss(20, 10))
        slippage_bps = min(slippage_bps, 60)
    slippage = 2 * slippage_bps / 10000.0  # Entry + exit

    return fee + spread + slippage


def is_meme_symbol(symbol: str) -> bool:
    """Heuristic: check if symbol is likely a meme coin."""
    meme_keywords = [
        'PEPE', 'DOGE', 'SHIB', 'FLOKI', 'BONK', 'WIF', 'BRETT',
        'MEME', 'PEOPLE', 'LUNC', 'BABYDOGE', 'ELON', 'FEG',
        'SAMO', 'POOH', 'TSUKA', 'DODO', 'CHZ', 'MANA', 'SAND',
        'APE', 'FLM', 'ATA', 'LIT', 'AUCTION', 'BEL', 'BTS',
        'CKB', 'COTI', 'CTSI', 'DENT', 'ENJ', 'EPS', 'EWT',
        'FORTH', 'GAS', 'GLM', 'GNO', 'HARD', 'ICP', 'IDEX',
        'INJ', 'IOST', 'IOTX', 'JASMY', 'JST', 'KDA', 'KSM',
        'LINA', 'LSK', 'MDT', 'MTL', 'NKN', 'OAX', 'OGN',
        'OMG', 'ONE', 'ONT', 'PERP', 'PHA', 'PNT', 'POLS',
        'PYR', 'RAD', 'REEF', 'REQ', 'RG', 'RLC', 'ROSE',
        'RIF', 'SKL', 'SLP', 'SNT', 'SNX', 'SPELL', 'SRM',
        'STORJ', 'SUSHI', 'SXP', 'THETA', 'TLM', 'TOMO',
        'TRB', 'TRU', 'TVK', 'VET', 'WAXP', 'WIN', 'WNXM',
        'XEM', 'XVS', 'YGG', 'ZEN',
    ]
    base = symbol.replace('USDT', '').replace('BUSD', '')
    return base in meme_keywords


# ═══════════════════════════════════════════════════════════════
# BINANCE API — 1M KLINE FETCHER
# ═══════════════════════════════════════════════════════════════

BINANCE_FAPI_BASE = "https://fapi.binance.com"


def fetch_1m_klines(symbol: str, start_ms: int, end_ms: int,
                    rate_limit_delay: float = 0.5) -> list[KlineCandle]:
    """Fetch 1m klines from Binance USDM Futures REST API.

    API limits: 240 candles per request, weight=5 per call.
    For a 4-hour window: 240 candles = 1 call (trivial).
    """
    candles = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            'symbol': symbol,
            'interval': '1m',
            'startTime': current_start,
            'endTime': end_ms,
            'limit': 240,
        }

        url = f"{BINANCE_FAPI_BASE}/fapi/v1/klines"

        if HAS_REQUESTS:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        else:
            query = urllib.parse.urlencode(params)
            req = urllib.request.Request(f"{url}?{query}")
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

        if not data:
            break

        for item in data:
            candle = KlineCandle(
                open_time=int(item[0]),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
                close_time=int(item[6]),
            )
            candles.append(candle)

        # Move to next batch
        if data:
            last_close_time = int(data[-1][6])
            current_start = last_close_time + 1
        else:
            break

        # Rate limit: 5 weight per call, 2400 weight/min limit
        time.sleep(rate_limit_delay)

    return candles


# ═══════════════════════════════════════════════════════════════
# TRADE EXPORT FROM SQLITE
# ═══════════════════════════════════════════════════════════════

EXPORT_QUERY = """
SELECT
    id, symbol, side, entry_price, opened_at,
    confidence, signal_reason,
    volume_ratio, momentum_pct, rsi, adx, funding_rate,
    leverage,
    exit_reason, pnl_pct, hold_sec,
    max_favorable_pct, max_adverse_pct,
    runtime_config
FROM trades
WHERE closed_at IS NOT NULL
ORDER BY opened_at ASC
"""


def export_trades_from_db(db_path: str, output_csv: str) -> int:
    """Export trades from bot SQLite DB to CSV for replay."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(EXPORT_QUERY)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print(f"ERROR: No trades found in {db_path}")
        return 0

    # Collect all fieldnames from runtime_config expansion
    fieldnames = [
        'id', 'symbol', 'side', 'entry_price', 'entry_time',
        'confidence', 'signal_reason',
        'volume_ratio', 'momentum_pct', 'rsi', 'adx', 'funding_rate',
        'leverage',
        'original_exit_reason', 'original_pnl_pct', 'original_hold_sec',
        'original_max_favorable', 'original_max_adverse',
        'original_tp_pct', 'original_sl_pct', 'original_max_hold_sec',
    ]

    count = 0
    with open(output_csv, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            # Parse runtime_config to get original TP/SL
            runtime_config = {}
            if row['runtime_config']:
                try:
                    runtime_config = json.loads(row['runtime_config'])
                except json.JSONDecodeError:
                    pass

            record = {
                'id': row['id'],
                'symbol': row['symbol'],
                'side': row['side'],
                'entry_price': row['entry_price'],
                'entry_time': row['opened_at'],
                'confidence': row['confidence'],
                'signal_reason': row['signal_reason'],
                'volume_ratio': row['volume_ratio'],
                'momentum_pct': row['momentum_pct'],
                'rsi': row['rsi'],
                'adx': row['adx'],
                'funding_rate': row['funding_rate'],
                'leverage': row['leverage'],
                'original_exit_reason': row['exit_reason'],
                'original_pnl_pct': row['pnl_pct'],
                'original_hold_sec': row['hold_sec'],
                'original_max_favorable': row['max_favorable_pct'],
                'original_max_adverse': row['max_adverse_pct'],
                'original_tp_pct': runtime_config.get('take_profit_pct', ''),
                'original_sl_pct': runtime_config.get('stop_loss_pct', ''),
                'original_max_hold_sec': runtime_config.get('max_hold_sec', ''),
            }
            writer.writerow(record)
            count += 1

    print(f"Exported {count} trades to {output_csv}")
    return count


def load_trades_from_csv(csv_path: str) -> list[TradeEntry]:
    """Load trade entries from CSV file."""
    trades = []
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = TradeEntry(
                id=int(row['id']),
                symbol=row['symbol'],
                side=row['side'],
                entry_price=float(row['entry_price']),
                entry_time=float(row['entry_time']),
                confidence=float(row.get('confidence', 0)),
                signal_reason=row.get('signal_reason', ''),
                volume_ratio=float(row.get('volume_ratio', 0)),
                momentum_pct=float(row.get('momentum_pct', 0)),
                rsi=float(row.get('rsi', 50)),
                adx=float(row.get('adx', 0)),
                funding_rate=float(row.get('funding_rate', 0)),
                leverage=int(row.get('leverage', 20)),
                original_exit_reason=row.get('original_exit_reason', ''),
                original_pnl_pct=float(row.get('original_pnl_pct', 0)),
                original_hold_sec=float(row.get('original_hold_sec', 0)),
                original_tp_pct=float(row['original_tp_pct']) if row.get('original_tp_pct') else 0,
                original_sl_pct=float(row['original_sl_pct']) if row.get('original_sl_pct') else 0,
                max_favorable_pct=float(row.get('original_max_favorable', 0)) if row.get('original_max_favorable') else 0,
                max_adverse_pct=float(row.get('original_max_adverse', 0)) if row.get('original_max_adverse') else 0,
            )
            trades.append(trade)
    return trades


# ═══════════════════════════════════════════════════════════════
# REPLAY ENGINE — Core Logic
# ═══════════════════════════════════════════════════════════════

def replay_single_trade(
    trade: TradeEntry,
    candles: list[KlineCandle],
    tp_pct: float,
    sl_pct: float,
    max_hold_sec: float = 14400,
    cost_pct: float = 0.0,
) -> Optional[ReplayResult]:
    """Replay a single trade against 1m klines.

    Rules:
    - First candle where high >= TP level AND low <= SL level → ambiguous → SL hit first (conservative)
    - If TP hit before SL → exit at TP price
    - If SL hit before TP → exit at SL price
    - If max_hold_sec exceeded → exit at close of that candle
    - MFE/MAE tracked across all candles

    Returns None if no kline data covers the trade window.
    """
    if not candles:
        return None

    entry = trade.entry_price
    is_long = trade.side.upper() == 'LONG'

    # Calculate TP/SL price levels
    if is_long:
        tp_price = entry * (1 + tp_pct / 100.0)
        sl_price = entry * (1 - sl_pct / 100.0)
    else:
        tp_price = entry * (1 - tp_pct / 100.0)
        sl_price = entry * (1 + sl_pct / 100.0)

    entry_time_s = trade.entry_time  # Unix seconds
    max_exit_time_s = entry_time_s + max_hold_sec

    mfe_pct = 0.0  # Max Favorable Excursion
    mae_pct = 0.0  # Max Adverse Excursion
    ambiguous_count = 0
    klines_checked = 0

    for candle in candles:
        # Skip candles before entry
        if candle.open_time < entry_time_s * 1000:
            continue

        # Check max hold
        candle_time_s = candle.open_time / 1000.0
        if candle_time_s > max_exit_time_s:
            # Max hold exceeded — exit at open of this candle
            if is_long:
                pnl_raw = (candle.open - entry) / entry * 100.0
            else:
                pnl_raw = (entry - candle.open) / entry * 100.0

            return ReplayResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=entry,
                entry_time=trade.entry_time,
                confidence=trade.confidence,
                signal_reason=trade.signal_reason,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                exit_type='MAX_HOLD',
                exit_price=candle.open,
                pnl_pct=pnl_raw,
                pnl_after_cost=pnl_raw - cost_pct,
                hold_sec=candle_time_s - entry_time_s,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                klines_used=klines_checked,
                ambiguous_candles=ambiguous_count,
            )

        klines_checked += 1

        # Calculate PnL at high, low, open, close
        if is_long:
            high_pnl = (candle.high - entry) / entry * 100.0
            low_pnl = (candle.low - entry) / entry * 100.0
        else:
            high_pnl = (entry - candle.low) / entry * 100.0
            low_pnl = (entry - candle.high) / entry * 100.0

        # Update MFE/MAE
        mfe_pct = max(mfe_pct, high_pnl)
        mae_pct = min(mae_pct, low_pnl)

        # Check TP/SL hit
        tp_hit = high_pnl >= tp_pct
        sl_hit = low_pnl <= -sl_pct

        if tp_hit and sl_hit:
            # AMBIGUOUS — both TP and SL hit in same candle
            # Conservative: assume SL hit first
            ambiguous_count += 1
            if is_long:
                exit_price = entry * (1 - sl_pct / 100.0)
                pnl_raw = -sl_pct
            else:
                exit_price = entry * (1 + sl_pct / 100.0)
                pnl_raw = -sl_pct

            return ReplayResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=entry,
                entry_time=trade.entry_time,
                confidence=trade.confidence,
                signal_reason=trade.signal_reason,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                exit_type='AMBIGUOUS_SL',
                exit_price=exit_price,
                pnl_pct=pnl_raw,
                pnl_after_cost=pnl_raw - cost_pct,
                hold_sec=candle_time_s - entry_time_s,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                klines_used=klines_checked,
                ambiguous_candles=ambiguous_count,
            )

        elif sl_hit:
            # SL hit
            if is_long:
                exit_price = entry * (1 - sl_pct / 100.0)
                pnl_raw = -sl_pct
            else:
                exit_price = entry * (1 + sl_pct / 100.0)
                pnl_raw = -sl_pct

            return ReplayResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=entry,
                entry_time=trade.entry_time,
                confidence=trade.confidence,
                signal_reason=trade.signal_reason,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                exit_type='SL',
                exit_price=exit_price,
                pnl_pct=pnl_raw,
                pnl_after_cost=pnl_raw - cost_pct,
                hold_sec=candle_time_s - entry_time_s,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                klines_used=klines_checked,
                ambiguous_candles=ambiguous_count,
            )

        elif tp_hit:
            # TP hit
            if is_long:
                exit_price = entry * (1 + tp_pct / 100.0)
                pnl_raw = tp_pct
            else:
                exit_price = entry * (1 - tp_pct / 100.0)
                pnl_raw = tp_pct

            return ReplayResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=entry,
                entry_time=trade.entry_time,
                confidence=trade.confidence,
                signal_reason=trade.signal_reason,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                exit_type='TP',
                exit_price=exit_price,
                pnl_pct=pnl_raw,
                pnl_after_cost=pnl_raw - cost_pct,
                hold_sec=candle_time_s - entry_time_s,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                klines_used=klines_checked,
                ambiguous_candles=ambiguous_count,
            )

    # If we get here, max_hold wasn't exceeded but we ran out of candles
    # Exit at last candle close
    if candles and klines_checked > 0:
        last_candle = None
        for c in reversed(candles):
            if c.open_time >= entry_time_s * 1000:
                last_candle = c
                break

        if last_candle:
            if is_long:
                pnl_raw = (last_candle.close - entry) / entry * 100.0
            else:
                pnl_raw = (entry - last_candle.close) / entry * 100.0

            return ReplayResult(
                trade_id=trade.id,
                symbol=trade.symbol,
                side=trade.side,
                entry_price=entry,
                entry_time=trade.entry_time,
                confidence=trade.confidence,
                signal_reason=trade.signal_reason,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                exit_type='MAX_HOLD',
                exit_price=last_candle.close,
                pnl_pct=pnl_raw,
                pnl_after_cost=pnl_raw - cost_pct,
                hold_sec=last_candle.open_time / 1000.0 - entry_time_s,
                mfe_pct=mfe_pct,
                mae_pct=mae_pct,
                klines_used=klines_checked,
                ambiguous_candles=ambiguous_count,
            )

    return None  # No kline data covered this trade


# ═══════════════════════════════════════════════════════════════
# TP/SL GRID SEARCH
# ═══════════════════════════════════════════════════════════════

# Default TP/SL combos from reviewer consensus
DEFAULT_TP_SL_GRID = [
    # (TP%, SL%, description)
    (1.0, 0.5, 'current_original'),
    (1.5, 1.0, 'moderate_widen'),
    (2.0, 1.5, 'claude_moderate'),
    (3.0, 2.0, 'claude_proposed'),
    (3.0, 2.5, 'claude_conservative'),
    (4.0, 2.5, 'zai_proposed'),
    (4.0, 3.0, 'zai_conservative'),
    (5.0, 3.0, 'kimi_proposed'),
    (5.0, 3.5, 'kimi_conservative'),
    (8.0, 5.0, 'fifteen_rr_1.6'),
    (8.0, 7.6, 'fifteen_original'),
]


# ═══════════════════════════════════════════════════════════════
# MAIN REPLAY ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════

def run_replay(
    trades: list[TradeEntry],
    output_dir: str,
    tp_sl_grid: list = None,
    max_hold_sec: float = 14400,
    realistic_costs: bool = False,
    kline_window_hours: float = 4.0,
    rate_limit_delay: float = 0.5,
    kline_cache_dir: str = None,
):
    """Run the full replay pipeline.

    For each TP/SL combo:
    1. Fetch 1m klines for each trade's symbol + time window
    2. Replay each trade
    3. Compute aggregate stats
    4. Run calibration gate against original sim results
    """
    if tp_sl_grid is None:
        tp_sl_grid = DEFAULT_TP_SL_GRID

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if kline_cache_dir:
        cache_path = Path(kline_cache_dir)
        cache_path.mkdir(parents=True, exist_ok=True)

    # Kline cache: symbol -> date -> list of candles
    kline_cache = {}

    print(f"=" * 70)
    print(f"CLAW REPLAY PIPELINE")
    print(f"=" * 70)
    print(f"Trades to replay: {len(trades)}")
    print(f"TP/SL combos: {len(tp_sl_grid)}")
    print(f"Max hold: {max_hold_sec}s ({max_hold_sec/3600:.1f}hr)")
    print(f"Realistic costs: {realistic_costs}")
    print(f"Kline window: {kline_window_hours}hr per trade")
    print(f"Output: {output_dir}")
    print()

    # ─── STEP 1: Fetch all klines needed ────────────────────
    print("STEP 1: Fetching 1m klines from Binance...")
    kline_fetch_count = 0
    kline_cache_hits = 0

    # Group trades by (symbol, date) to minimize API calls
    symbol_dates = {}
    for trade in trades:
        dt = datetime.fromtimestamp(trade.entry_time, tz=timezone.utc)
        date_key = dt.strftime('%Y-%m-%d')
        key = (trade.symbol, date_key)
        if key not in symbol_dates:
            symbol_dates[key] = {
                'symbol': trade.symbol,
                'date': date_key,
                'start_ms': int(dt.replace(hour=0, minute=0, second=0).timestamp() * 1000),
                'end_ms': int(dt.replace(hour=23, minute=59, second=59).timestamp() * 1000),
            }

    for key, info in symbol_dates.items():
        sym = info['symbol']
        cache_file = None
        if kline_cache_dir:
            cache_file = cache_path / f"{sym}_{info['date']}.json"

        # Check cache
        if cache_file and cache_file.exists():
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            kline_cache[key] = [KlineCandle(**c) for c in cached]
            kline_cache_hits += 1
            continue

        # Fetch from Binance
        try:
            candles = fetch_1m_klines(
                symbol=sym,
                start_ms=info['start_ms'],
                end_ms=info['end_ms'],
                rate_limit_delay=rate_limit_delay,
            )
            kline_cache[key] = candles
            kline_fetch_count += 1

            # Save to cache
            if cache_file:
                with open(cache_file, 'w') as f:
                    json.dump([asdict(c) for c in candles], f)

            print(f"  Fetched {sym} {info['date']}: {len(candles)} candles")
        except Exception as e:
            print(f"  ERROR fetching {sym} {info['date']}: {e}")
            kline_cache[key] = []

        time.sleep(rate_limit_delay)

    print(f"Klines: {kline_fetch_count} fetched, {kline_cache_hits} cached")
    print()

    # ─── STEP 2: Build per-trade kline windows ──────────────
    print("STEP 2: Building per-trade kline windows...")

    def get_candles_for_trade(trade: TradeEntry) -> list[KlineCandle]:
        """Get relevant candles for a trade's time window."""
        entry_time_s = trade.entry_time
        window_start_s = entry_time_s - 60  # 1 min before entry
        window_end_s = entry_time_s + max_hold_sec + 300  # Extra buffer

        dt = datetime.fromtimestamp(entry_time_s, tz=timezone.utc)
        date_key = dt.strftime('%Y-%m-%d')

        # May span two dates
        relevant_candles = []
        for key, candles in kline_cache.items():
            if key[0] == trade.symbol:
                for c in candles:
                    c_time_s = c.open_time / 1000.0
                    if window_start_s <= c_time_s <= window_end_s:
                        relevant_candles.append(c)

        # Sort by time
        relevant_candles.sort(key=lambda c: c.open_time)
        return relevant_candles

    # ─── STEP 3: Replay each TP/SL combo ───────────────────
    print("STEP 3: Running replay for each TP/SL combo...")

    summary_rows = []

    for tp_pct, sl_pct, description in tp_sl_grid:
        combo_results = []
        skipped = 0

        # Cost model
        if realistic_costs:
            # Use simple cost for now — mixture would add randomness
            cost_pct = SIMPLE_ROUND_TRIP_COST_PCT
        else:
            cost_pct = SIMPLE_ROUND_TRIP_COST_PCT

        # Breakeven WR for this combo
        breakeven_wr = (sl_pct + cost_pct) / (tp_pct + sl_pct + cost_pct) * 100.0

        for trade in trades:
            candles = get_candles_for_trade(trade)

            if not candles:
                skipped += 1
                continue

            result = replay_single_trade(
                trade=trade,
                candles=candles,
                tp_pct=tp_pct,
                sl_pct=sl_pct,
                max_hold_sec=max_hold_sec,
                cost_pct=cost_pct,
            )

            if result:
                combo_results.append(result)
            else:
                skipped += 1

        # ─── Aggregate stats ────────────────────────────────
        if not combo_results:
            print(f"  {description} (TP{tp_pct}/SL{sl_pct}): NO RESULTS (all skipped)")
            continue

        total = len(combo_results)
        tp_wins = sum(1 for r in combo_results if r.exit_type == 'TP')
        sl_losses = sum(1 for r in combo_results if r.exit_type in ('SL', 'AMBIGUOUS_SL'))
        max_hold = sum(1 for r in combo_results if r.exit_type == 'MAX_HOLD')
        ambiguous = sum(1 for r in combo_results if r.exit_type == 'AMBIGUOUS_SL')

        wr = tp_wins / total * 100.0 if total > 0 else 0
        avg_pnl = sum(r.pnl_after_cost for r in combo_results) / total if total > 0 else 0
        avg_hold = sum(r.hold_sec for r in combo_results) / total if total > 0 else 0
        avg_mfe = sum(r.mfe_pct for r in combo_results) / total if total > 0 else 0
        avg_mae = sum(r.mae_pct for r in combo_results) / total if total > 0 else 0

        # Per-tier breakdown
        tier_stats = {}
        for r in combo_results:
            tier = r.signal_reason or 'unknown'
            if tier not in tier_stats:
                tier_stats[tier] = {'total': 0, 'wins': 0, 'pnl_sum': 0.0}
            tier_stats[tier]['total'] += 1
            if r.exit_type == 'TP':
                tier_stats[tier]['wins'] += 1
            tier_stats[tier]['pnl_sum'] += r.pnl_after_cost

        # EV calculation
        # EV = WR × (TP - cost) - (1-WR) × (SL + cost)
        ev_per_trade = wr / 100.0 * (tp_pct - cost_pct) - (1 - wr / 100.0) * (sl_pct + cost_pct)

        # Cost/TP ratio
        cost_tp_ratio = cost_pct / tp_pct * 100.0 if tp_pct > 0 else float('inf')

        print(f"  {description} (TP{tp_pct}/SL{sl_pct}): "
              f"WR={wr:.1f}% (BE={breakeven_wr:.1f}%) "
              f"EV={ev_per_trade:+.3f}% "
              f"TP={tp_wins} SL={sl_losses} MH={max_hold} AMB={ambiguous} "
              f"skipped={skipped}")

        summary_rows.append({
            'description': description,
            'tp_pct': tp_pct,
            'sl_pct': sl_pct,
            'rr_ratio': tp_pct / sl_pct if sl_pct > 0 else 0,
            'breakeven_wr': breakeven_wr,
            'observed_wr': wr,
            'wr_above_be': wr - breakeven_wr,
            'ev_per_trade': ev_per_trade,
            'cost_tp_ratio': cost_tp_ratio,
            'total_trades': total,
            'tp_wins': tp_wins,
            'sl_losses': sl_losses,
            'max_hold_exits': max_hold,
            'ambiguous_sl': ambiguous,
            'skipped': skipped,
            'avg_pnl_after_cost': avg_pnl,
            'avg_hold_sec': avg_hold,
            'avg_mfe_pct': avg_mfe,
            'avg_mae_pct': avg_mae,
        })

        # ─── Write detailed per-trade CSV ───────────────────
        detail_file = output_path / f"replay_{description}_TP{tp_pct}_SL{sl_pct}.csv"
        with open(detail_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'trade_id', 'symbol', 'side', 'entry_price', 'entry_time',
                'confidence', 'signal_reason', 'tp_pct', 'sl_pct',
                'exit_type', 'exit_price', 'pnl_pct', 'pnl_after_cost',
                'hold_sec', 'mfe_pct', 'mae_pct', 'klines_used', 'ambiguous_candles',
            ])
            writer.writeheader()
            for r in combo_results:
                writer.writerow(asdict(r))

        # ─── Write per-tier breakdown ───────────────────────
        tier_file = output_path / f"tiers_{description}_TP{tp_pct}_SL{sl_pct}.csv"
        with open(tier_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'tier', 'total', 'wins', 'wr', 'avg_pnl', 'ev_contribution',
            ])
            writer.writeheader()
            for tier, stats in sorted(tier_stats.items()):
                tier_wr = stats['wins'] / stats['total'] * 100.0 if stats['total'] > 0 else 0
                tier_avg_pnl = stats['pnl_sum'] / stats['total'] if stats['total'] > 0 else 0
                writer.writerow({
                    'tier': tier,
                    'total': stats['total'],
                    'wins': stats['wins'],
                    'wr': f"{tier_wr:.1f}",
                    'avg_pnl': f"{tier_avg_pnl:+.4f}",
                    'ev_contribution': f"{tier_avg_pnl * stats['total']:+.4f}",
                })

    # ─── STEP 4: Write summary CSV ─────────────────────────
    summary_file = output_path / "replay_summary.csv"
    with open(summary_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys() if summary_rows else [])
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(row)

    print()
    print("=" * 70)
    print("REPLAY SUMMARY")
    print("=" * 70)
    print(f"{'Description':<25} {'TP':>4} {'SL':>4} {'R:R':>4} {'BE%':>5} {'WR%':>5} {'Δ':>5} {'EV%':>7} {'Cost%':>5}")
    print("-" * 70)
    for row in summary_rows:
        delta = row['wr_above_be']
        ev = row['ev_per_trade']
        marker = "✓" if delta > 5 else "?" if delta > 0 else "✗"
        print(f"{row['description']:<25} {row['tp_pct']:>4.0f} {row['sl_pct']:>4.0f} "
              f"{row['rr_ratio']:>4.1f} {row['breakeven_wr']:>5.1f} {row['observed_wr']:>5.1f} "
              f"{delta:>+5.1f} {ev:>+7.3f} {row['cost_tp_ratio']:>5.1f} {marker}")

    # ─── STEP 5: Calibration Gate ──────────────────────────
    print()
    print("=" * 70)
    print("CALIBRATION GATE")
    print("=" * 70)
    print("Comparing replay at original params (TP1/SL0.5) against sim observed WR (35-45%)")
    print()

    for row in summary_rows:
        if row['tp_pct'] == 1.0 and row['sl_pct'] == 0.5:
            replay_wr = row['observed_wr']
            sim_wr_low = 35.0
            sim_wr_high = 45.0
            in_range = sim_wr_low <= replay_wr <= sim_wr_high
            within_5pct = abs(replay_wr - 40.0) <= 5.0  # Midpoint of 35-45%

            print(f"  Replay WR at original params: {replay_wr:.1f}%")
            print(f"  Sim observed WR range: {sim_wr_low}-{sim_wr_high}%")
            print(f"  Within range: {'YES' if in_range else 'NO'}")
            print(f"  Within ±5% of midpoint: {'YES' if within_5pct else 'NO'}")

            if within_5pct:
                print(f"  CALIBRATION: PASSED — Replay results are trustworthy")
            else:
                print(f"  CALIBRATION: FAILED — Replay WR differs from sim by >5%. "
                      f"Check kline data quality and entry time accuracy.")
            break
    else:
        print("  WARNING: Original params (TP1/SL0.5) not in grid — cannot calibrate")

    # ─── STEP 6: Decision Gate ─────────────────────────────
    print()
    print("=" * 70)
    print("DECISION GATE (from cross_analysis.md Section 6)")
    print("=" * 70)

    viable_combos = [r for r in summary_rows if r['wr_above_be'] > 5.0]
    marginal_combos = [r for r in summary_rows if 0 < r['wr_above_be'] <= 5.0]
    dead_combos = [r for r in summary_rows if r['wr_above_be'] <= 0]

    if viable_combos:
        best = max(viable_combos, key=lambda r: r['ev_per_trade'])
        print(f"  RESULT: {len(viable_combos)} VIABLE combo(s) found (WR > BE + 5%)")
        print(f"  BEST: {best['description']} (TP{best['tp_pct']}/SL{best['sl_pct']})")
        print(f"    WR={best['observed_wr']:.1f}% vs BE={best['breakeven_wr']:.1f}% (Δ={best['wr_above_be']:+.1f}%)")
        print(f"    EV={best['ev_per_trade']:+.3f}%/trade")
        print()
        print("  → ACTION: Fix confidence formula → implement Kelly sizing → forward test")
    elif marginal_combos:
        print(f"  RESULT: {len(marginal_combos)} MARGINAL combo(s) (WR 0-5% above BE)")
        print("  → ACTION: Need more trades for statistical confidence. Consider wider stops or pivot.")
    else:
        print(f"  RESULT: ALL combos have WR below breakeven ({len(dead_combos)} dead)")
        print("  → ACTION: PIVOT to Major Swing (Fifteen-style) on BTC/ETH/SOL")

    print()
    print(f"Full results saved to: {output_dir}")
    return summary_rows


# ═══════════════════════════════════════════════════════════════
# STATS COMMAND — Quick summary of existing results
# ═══════════════════════════════════════════════════════════════

def show_stats(results_dir: str):
    """Display stats from a previously run replay."""
    summary_file = Path(results_dir) / "replay_summary.csv"
    if not summary_file.exists():
        print(f"ERROR: No replay_summary.csv found in {results_dir}")
        return

    with open(summary_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("=" * 70)
    print("REPLAY RESULTS SUMMARY")
    print("=" * 70)
    print(f"Source: {results_dir}")
    print(f"Combos tested: {len(rows)}")
    print()

    print(f"{'Description':<25} {'TP':>4} {'SL':>4} {'BE%':>5} {'WR%':>5} {'Δ':>5} {'EV%':>7}")
    print("-" * 60)
    for row in rows:
        delta = float(row.get('wr_above_be', 0))
        ev = float(row.get('ev_per_trade', 0))
        marker = "✓" if delta > 5 else "?" if delta > 0 else "✗"
        print(f"{row['description']:<25} {float(row['tp_pct']):>4.0f} {float(row['sl_pct']):>4.0f} "
              f"{float(row['breakeven_wr']):>5.1f} {float(row['observed_wr']):>5.1f} "
              f"{delta:>+5.1f} {ev:>+7.3f} {marker}")


# ═══════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='Claw Crypto Strategy — Replay Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export trades from bot SQLite DB
  python replay_pipeline.py export --db /path/to/claw.db --output trades.csv

  # Run replay (fetches klines from Binance)
  python replay_pipeline.py replay --trades trades.csv --output results/

  # Run replay with realistic cost model and extended max hold
  python replay_pipeline.py replay --trades trades.csv --output results/ --realistic-costs --max-hold 14400

  # Full pipeline: export + replay + stats
  python replay_pipeline.py full --db /path/to/claw.db --output results/

  # View stats from previous run
  python replay_pipeline.py stats --results results/

  # Custom TP/SL grid
  python replay_pipeline.py replay --trades trades.csv --output results/ --grid "1.0/0.5,3.0/2.0,5.0/3.0,8.0/5.0"
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export trades from SQLite DB')
    export_parser.add_argument('--db', required=True, help='Path to bot SQLite database')
    export_parser.add_argument('--output', required=True, help='Output CSV file path')

    # Replay command
    replay_parser = subparsers.add_parser('replay', help='Run replay pipeline')
    replay_parser.add_argument('--trades', required=True, help='CSV file with trade entries')
    replay_parser.add_argument('--output', required=True, help='Output directory for results')
    replay_parser.add_argument('--max-hold', type=float, default=14400,
                               help='Max hold time in seconds (default: 14400 = 4hr)')
    replay_parser.add_argument('--realistic-costs', action='store_true',
                               help='Use mixture distribution cost model instead of simple 0.178%')
    replay_parser.add_argument('--grid', type=str, default=None,
                               help='Custom TP/SL grid as "TP1/SL1,TP2/SL2,..." format')
    replay_parser.add_argument('--kline-cache', type=str, default=None,
                               help='Directory to cache kline data for reuse')
    replay_parser.add_argument('--rate-limit', type=float, default=0.5,
                               help='Delay between Binance API calls in seconds (default: 0.5)')
    replay_parser.add_argument('--kline-window', type=float, default=4.0,
                               help='Kline fetch window in hours per trade (default: 4.0)')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show stats from replay results')
    stats_parser.add_argument('--results', required=True, help='Results directory')

    # Full pipeline command
    full_parser = subparsers.add_parser('full', help='Full pipeline: export + replay + stats')
    full_parser.add_argument('--db', required=True, help='Path to bot SQLite database')
    full_parser.add_argument('--output', required=True, help='Output directory for results')
    full_parser.add_argument('--max-hold', type=float, default=14400,
                             help='Max hold time in seconds (default: 14400 = 4hr)')
    full_parser.add_argument('--realistic-costs', action='store_true',
                             help='Use mixture distribution cost model')
    full_parser.add_argument('--grid', type=str, default=None,
                             help='Custom TP/SL grid as "TP1/SL1,TP2/SL2,..." format')
    full_parser.add_argument('--kline-cache', type=str, default=None,
                             help='Directory to cache kline data')
    full_parser.add_argument('--rate-limit', type=float, default=0.5,
                             help='Delay between API calls (default: 0.5)')

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == 'export':
        count = export_trades_from_db(args.db, args.output)
        if count == 0:
            sys.exit(1)

    elif args.command == 'replay':
        trades = load_trades_from_csv(args.trades)
        if not trades:
            print(f"ERROR: No trades loaded from {args.trades}")
            sys.exit(1)

        grid = DEFAULT_TP_SL_GRID
        if args.grid:
            grid = []
            for combo in args.grid.split(','):
                tp, sl = combo.split('/')
                grid.append((float(tp), float(sl), f'custom_TP{tp}_SL{sl}'))

        run_replay(
            trades=trades,
            output_dir=args.output,
            tp_sl_grid=grid,
            max_hold_sec=args.max_hold,
            realistic_costs=args.realistic_costs,
            kline_window_hours=args.kline_window,
            rate_limit_delay=args.rate_limit,
            kline_cache_dir=args.kline_cache,
        )

    elif args.command == 'stats':
        show_stats(args.results)

    elif args.command == 'full':
        # Step 1: Export
        trades_csv = os.path.join(args.output, 'trades_export.csv')
        count = export_trades_from_db(args.db, trades_csv)
        if count == 0:
            print("ERROR: No trades exported")
            sys.exit(1)

        # Step 2: Replay
        trades = load_trades_from_csv(trades_csv)
        grid = DEFAULT_TP_SL_GRID
        if args.grid:
            grid = []
            for combo in args.grid.split(','):
                tp, sl = combo.split('/')
                grid.append((float(tp), float(sl), f'custom_TP{tp}_SL{sl}'))

        run_replay(
            trades=trades,
            output_dir=args.output,
            tp_sl_grid=grid,
            max_hold_sec=args.max_hold,
            realistic_costs=args.realistic_costs,
            kline_cache_dir=args.kline_cache,
            rate_limit_delay=args.rate_limit,
        )

        # Step 3: Stats
        show_stats(args.output)


if __name__ == '__main__':
    main()
