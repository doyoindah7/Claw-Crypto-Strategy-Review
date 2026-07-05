"""
Position Management — Exit Logic & Trailing Stops
===================================================
Pseudocode extracted from PaperPosition and Bot._close_position()

The exit logic is just as important as entry — perhaps more so.
"""

class PaperPosition:
    """Tracks an open position and determines when to exit."""
    
    # ─── Exit Check (called every 2 seconds) ────────────────
    def should_exit(self) -> Optional[str]:
        """Check if position should be closed. Returns exit reason or None.
        
        Priority: SL > Trailing > TP > Max Hold
        """
        
        # Skip if no price update yet
        if self.unrealized_pnl_pct == 0:
            return None
        
        # ── Priority 1: Stop Loss (always checked first) ────
        if self.unrealized_pnl_pct <= -self.stop_loss_pct:
            return "SL_HIT"
        
        # ── Priority 2: Trailing Stop ───────────────────────
        # Only exits if trail level ≥ TP level
        # This prevents trailing from exiting BELOW TP
        if self.trailing_active:
            trail_exit_level = self.highest_pnl_pct - self.trailing_stop_pct
            
            if trail_exit_level >= self.take_profit_pct:
                # Trail level is above TP — safe to use trailing stop
                if self.unrealized_pnl_pct < trail_exit_level:
                    return "TRAILING_STOP"
            # If trail level < TP, fall through to fixed TP check
        
        # ── Priority 3: Take Profit ─────────────────────────
        if self.unrealized_pnl_pct >= self.take_profit_pct:
            return "TP_HIT"
        
        # ── Priority 4: Max Hold Time ───────────────────────
        held_sec = time() - self.invested_at
        if held_sec >= self.max_hold_sec:
            return "MAX_HOLD"
        
        return None  # Hold the position
    
    # ─── Price Update (called every 2 seconds) ──────────────
    def update_price(self, current_price):
        """Update position with new price, track metrics."""
        self.current_price = current_price
        self.price_updates += 1
        
        # Calculate unrealized PnL%
        if self.side == "LONG":
            self.unrealized_pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:  # SHORT
            self.unrealized_pnl_pct = (self.entry_price - current_price) / self.entry_price * 100
        
        # Calculate unrealized PnL in USD
        self.unrealized_pnl = self.margin_usd * self.leverage * (self.unrealized_pnl_pct / 100)
        
        # Track highest PnL for trailing stop
        if self.unrealized_pnl_pct > self.highest_pnl_pct:
            self.highest_pnl_pct = self.unrealized_pnl_pct
        
        # Track max favorable/adverse excursion (for backtest analysis)
        if self.unrealized_pnl_pct > self.max_favorable_pct:
            self.max_favorable_pct = self.unrealized_pnl_pct
        if self.unrealized_pnl_pct < self.max_adverse_pct:
            self.max_adverse_pct = self.unrealized_pnl_pct
        
        # Check if TP/SL WOULD have been hit (signal accuracy tracking)
        if self.unrealized_pnl_pct >= self.take_profit_pct:
            self.tp_would_hit = True
        if self.unrealized_pnl_pct <= -self.stop_loss_pct:
            self.sl_would_hit = True
        
        # Activate trailing stop when PnL reaches activation threshold
        if self.unrealized_pnl_pct >= self.trailing_activation_pct and not self.trailing_active:
            self.trailing_active = True
        
        # Update trailing stop price
        if self.trailing_active:
            if self.side == "LONG":
                self.trailing_stop_price = self.entry_price * (
                    1 + (self.highest_pnl_pct - self.trailing_stop_pct) / 100
                )
            else:
                self.trailing_stop_price = self.entry_price * (
                    1 - (self.highest_pnl_pct - self.trailing_stop_pct) / 100
                )


# ─── Close Position Logic ────────────────────────────────────

def close_position(pos, reason, exit_price):
    """Close a position with realistic execution and PnL calculation."""
    
    # ─── Determine Exit Price ───────────────────────────────
    if reason in ("SL_HIT", "TP_HIT"):
        # Stop-limit order → exact trigger price
        # No spread, no slippage (exchange guarantee)
        if reason == "SL_HIT":
            target_pct = -pos.stop_loss_pct
        else:
            target_pct = pos.take_profit_pct
        
        if pos.side == "LONG":
            actual_exit_price = pos.entry_price * (1 + target_pct / 100)
        else:
            actual_exit_price = pos.entry_price * (1 - target_pct / 100)
        
        # Only fee on exit (no spread/slippage for stop-limit)
        exit_fee = pos.notional_usd * taker_fee_pct / 100
        exit_slippage_bps = 0.0
    else:
        # MAX_HOLD / TRAILING_STOP → market order
        # Full spread + slippage simulation
        exit_result = simulate_exit(pos.symbol, pos.side, exit_price, pos.notional_usd)
        actual_exit_price = exit_result.fill_price
        exit_fee = exit_result.fee_usd
        exit_slippage_bps = exit_result.slippage_bps
    
    # ─── Calculate PnL ──────────────────────────────────────
    if pos.side == "LONG":
        gross_pnl_pct = (actual_exit_price - pos.entry_price) / pos.entry_price * 100
    else:
        gross_pnl_pct = (pos.entry_price - actual_exit_price) / pos.entry_price * 100
    
    actual_pnl = pos.margin_usd * pos.leverage * (gross_pnl_pct / 100)
    
    # Total fees = entry fee + exit fee
    total_fees = pos.entry_fee_usd + exit_fee
    
    # Net PnL after all fees
    net_pnl = actual_pnl - total_fees
    
    # Fee impact as % of notional
    fee_impact_pct = (total_fees / pos.notional_usd * 100) if pos.notional_usd > 0 else 0
    
    # Net PnL% = gross - fee impact
    net_pnl_pct = gross_pnl_pct - fee_impact_pct
    
    # ─── Update Balance ─────────────────────────────────────
    balance += pos.margin_usd + net_pnl
    
    # ─── Record Trade ───────────────────────────────────────
    trade = TradeRecord(
        symbol=pos.symbol,
        side=pos.side,
        entry_price=pos.entry_price,
        exit_price=actual_exit_price,
        pnl_usd=net_pnl,
        pnl_pct=net_pnl_pct,
        gross_pnl_pct=gross_pnl_pct,
        fee_impact_pct=fee_impact_pct,
        exit_reason=reason,
        # ... plus all indicator values, execution details, and runtime config
    )
    
    return trade


# ─── Trailing Stop Example Walkthrough ───────────────────────
#
# Config: TP=1.0%, SL=0.5%, trail_act=0.6%, trail=0.25%
#
# Time  PnL%    Action
# ────────────────────────────────────────────────
# 0s    +0.00%  Position opened
# 10s   +0.20%  Hold
# 20s   +0.50%  Hold (almost at trail activation)
# 30s   +0.60%  🔔 Trailing ACTIVATED (PnL ≥ trail_act)
# 40s   +0.80%  Trail level = 0.80 - 0.25 = 0.55% (< TP, so no trail exit)
# 50s   +1.00%  TP_HIT! Fixed TP triggers (trail level 0.75% < TP 1.0%)
#
# Alternative path:
# 50s   +1.30%  Trail level = 1.30 - 0.25 = 1.05% (≥ TP 1.0%)
# 60s   +1.10%  PnL < trail level (1.05%) → TRAILING_STOP at +1.05%
#               ✅ Locks in MORE than fixed TP!
#
# Another path (trailing prevents premature exit):
# 40s   +0.80%  Trail level = 0.55% (< TP 1.0%)
# 50s   +0.40%  PnL drops, but trail level 0.55% < TP 1.0%
#               → NO trail exit, fall through to TP check
#               → PnL 0.40% < TP 1.0% → hold
#               ✅ Correctly prevents exiting below TP!


# ─── Slider Change Behavior ──────────────────────────────────
#
# When dashboard slider changes SL from 0.7% → 0.5%:
#
# BEFORE FIX:
#   - New positions use SL=0.5%
#   - Existing positions still use SL=0.7% (set at open time)
#   - Result: SL exits at -0.80% (0.7% + 0.10% fees)
#   - User sees -0.80% and wonders why SL at 0.5% didn't work
#
# AFTER FIX:
#   - New positions use SL=0.5%
#   - Existing positions ALSO update to SL=0.5% immediately
#   - Result: SL exits at -0.60% (0.5% + 0.10% fees)
#   - Consistent with user expectations
#
# Exception: Leverage cannot be changed on open positions
# (in real Binance futures, you can't change leverage mid-position)
