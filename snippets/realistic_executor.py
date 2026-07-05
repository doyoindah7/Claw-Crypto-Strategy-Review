"""
Realistic Paper Trading Executor
=================================
Pseudocode extracted from RealisticPaperExecutor

Simulates the gap between naive paper trading and live trading.
If you can't profit here, you won't profit in live.
"""

# ─── Configuration ────────────────────────────────────────────

DEFAULTS = {
    "spread_bps": 5.0,                  # Base bid-ask spread
    "slippage_bps_mean": 1.5,           # Mean slippage (Gaussian)
    "slippage_bps_std": 1.0,            # Std dev of slippage
    "slippage_bps_max": 5.0,            # Cap on slippage
    "fill_probability": 0.97,           # 97% fill rate (3% rejected)
    "partial_fill_probability": 0.08,   # 8% chance of partial fill
    "partial_fill_min_ratio": 0.6,      # Min 60% fill if partial
    "min_notional_usd": 5.0,            # Binance minimum order
    "latency_ms_mean": 8.0,             # Mean execution latency
    "latency_ms_std": 4.0,              # Std dev of latency
    "latency_ms_min": 2.0,              # Minimum latency
    "taker_fee_pct": 0.050,             # 0.05% per side (NOT maker 0.02%)
    "meme_spread_multiplier": 2.5,      # Wider spread for meme coins
    "meme_symbols": {"PEPEUSDT", "FLOKIUSDT", "BONKUSDT", "WIFUSDT", ...},
    "new_listing_spread_multiplier": 2.0,
}


def simulate_entry(symbol, side, price, notional_usd, 
                   is_new_listing=False, is_meme=False) -> ExecutionResult:
    """Simulate a market order ENTRY with realistic execution."""
    
    # ─── 1. Minimum Notional Check ──────────────────────────
    if notional_usd < 5.0:
        return REJECT(f"MIN_NOTIONAL: ${notional_usd:.2f} < $5.00")
    
    # ─── 2. Fill Probability ────────────────────────────────
    if random() > 0.97:
        reason = choice(["INSUFFICIENT_LIQUIDITY", "PRICE_LIMIT_EXCEEDED", 
                         "MARKET_CLOSED", "SYSTEM_BUSY"])
        return REJECT(reason)
    
    # ─── 3. Calculate Effective Spread ──────────────────────
    spread_bps = 5.0
    if symbol in MEME_SYMBOLS:
        spread_bps *= 2.5       # 12.5 bps for meme
    if is_new_listing:
        spread_bps *= 2.0       # Additional 2× for new listings
    
    half_spread_pct = spread_bps / 100 / 2  # Convert bps → % → half
    
    # Spread moves fill price AGAINST us:
    #   LONG: we buy at ASK (higher than mid) → worse entry
    #   SHORT: we sell at BID (lower than mid) → worse entry
    if side == "LONG":
        spread_price = price * (1 + half_spread_pct / 100)
    else:
        spread_price = price * (1 - half_spread_pct / 100)
    
    spread_cost_usd = notional_usd * half_spread_pct / 100
    
    # ─── 4. Add Slippage ────────────────────────────────────
    # Always adverse (worse for us)
    slippage_bps = min(
        slippage_bps_max,                           # Cap
        abs(gauss(mean=1.5, std=1.0))               # Gaussian random
    )
    slippage_pct = slippage_bps / 100  # bps → %
    
    if side == "LONG":
        fill_price = spread_price * (1 + slippage_pct / 100)   # Higher = worse
    else:
        fill_price = spread_price * (1 - slippage_pct / 100)   # Lower = worse
    
    # ─── 5. Partial Fill ────────────────────────────────────
    fill_qty_ratio = 1.0
    if random() < 0.08:
        fill_qty_ratio = uniform(0.6, 0.99)   # 60-99% fill
    
    fill_notional = notional_usd * fill_qty_ratio
    
    # ─── 6. Fee ─────────────────────────────────────────────
    fee_usd = fill_notional * 0.050 / 100     # Taker fee: 0.05%
    
    return ExecutionResult(
        filled=True,
        fill_price=fill_price,
        fill_qty_ratio=fill_qty_ratio,
        fill_notional=fill_notional,
        spread_cost_usd=spread_cost_usd,
        slippage_bps=slippage_bps,
        fee_usd=fee_usd,
    )


def simulate_exit(symbol, side, price, notional_usd, 
                  is_new_listing=False) -> ExecutionResult:
    """Simulate a market order EXIT with realistic execution.
    
    Key differences from entry:
    - 99% fill rate (slightly higher — closing is easier)
    - No partial fills (simplified)
    - Spread direction REVERSED:
        Exit LONG = sell at BID (lower) → worse exit
        Exit SHORT = buy at ASK (higher) → worse exit
    """
    if random() > 0.99:
        return REJECT("EXIT_REJECTED")
    
    # Same spread calculation as entry
    spread_bps = get_effective_spread_bps(symbol, is_new_listing)
    half_spread_pct = spread_bps / 100 / 2
    
    # REVERSED spread direction for exit
    if side == "LONG":
        spread_price = price * (1 - half_spread_pct / 100)   # Sell at BID
    else:
        spread_price = price * (1 + half_spread_pct / 100)   # Buy at ASK
    
    spread_cost_usd = notional_usd * half_spread_pct / 100
    
    # Same slippage model (adverse)
    slippage_bps = min(5.0, abs(gauss(1.5, 1.0)))
    slippage_pct = slippage_bps / 100
    
    if side == "LONG":
        fill_price = spread_price * (1 - slippage_pct / 100)  # Lower = worse exit
    else:
        fill_price = spread_price * (1 + slippage_pct / 100)  # Higher = worse exit
    
    fee_usd = notional_usd * 0.050 / 100
    
    return ExecutionResult(
        filled=True,
        fill_price=fill_price,
        fill_qty_ratio=1.0,  # No partial fills on exit
        fill_notional=notional_usd,
        spread_cost_usd=spread_cost_usd,
        slippage_bps=slippage_bps,
        fee_usd=fee_usd,
    )


# ─── Special Case: SL/TP Exits ────────────────────────────────
# These are handled DIFFERENTLY in the bot — not via simulate_exit():
#
# SL_HIT / TP_HIT → exact trigger price (like exchange stop-limit)
#   - No spread, no slippage (stop-limit guarantees price)
#   - Only taker fee is charged
#   - Exit price is calculated from entry_price and target PnL%
#
# MAX_HOLD / TRAILING_STOP → full simulate_exit() (market order)
#   - Spread + slippage + taker fee
#   - This is a market order, no price guarantee
#
# Example: SL at 0.5% on LONG position
#   trigger_price = entry_price * (1 - 0.5/100)
#   exit_fee = notional * 0.05%
#   gross_pnl_pct = -0.5%
#   net_pnl_pct = -0.5% - 0.10% (round-trip fees) = -0.6%
#
# This is WHY you see SL exits at 0.6%+ when SL is set to 0.5%:
#   The fee impact (0.10% round-trip) is added on top of the trigger level.


# ─── Round-Trip Cost Breakdown ────────────────────────────────
#
# For a MEME COIN trade with SL/TP exit:
#   Entry:  half_spread(6.25bps) + slippage(~1.5bps) + fee(5bps) = 12.75 bps
#   Exit:   fee only (5bps) = 5 bps
#   TOTAL:  17.75 bps = 0.178%
#
# For a MEME COIN trade with trailing stop (market exit):
#   Entry:  12.75 bps
#   Exit:   half_spread(6.25bps) + slippage(~1.5bps) + fee(5bps) = 12.75 bps
#   TOTAL:  25.5 bps = 0.255%
#
# Breakeven with TP=1.0%, SL=0.5% (meme, SL/TP exit):
#   Required winrate = 0.678 / (0.822 + 0.678) = 45.2%
