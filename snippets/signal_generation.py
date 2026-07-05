"""
Signal Generation Pipeline — 8-Tier Signal Evaluation
=====================================================
Pseudocode extracted from MemeScalpStrategy.evaluate()

This is the CORE of the bot: decide whether to trade, which direction,
and with what confidence.
"""

def evaluate(symbol, is_new_listing=False, price_change_24h=0.0) -> Optional[Signal]:
    """Evaluate a symbol for trading signal. Returns Signal or None."""
    
    # ─── Step 1: Cooldown Check ─────────────────────────────
    if symbol in cooldown and time() - cooldown[symbol] < 15:
        return None  # Wait 15s after last trade on this symbol
    
    # ─── Step 2: Fetch Klines ───────────────────────────────
    klines = api.get_klines(symbol, interval="5m", limit=60)
    if len(klines) < rsi_period + adx_period + 5:
        return None  # Not enough data
    
    # Extract OHLCV arrays
    closes = [k.close for k in klines]
    highs  = [k.high for k in klines]
    lows   = [k.low for k in klines]
    volumes = [k.quote_volume for k in klines]
    
    # ─── Step 3: Calculate Indicators ───────────────────────
    volume_ratio = volumes[-1] / mean(volumes[-31:-1])  # Current vs 30-candle avg
    
    momentum = (closes[-1] - closes[-1 - momentum_candles]) / closes[-1 - momentum_candles] * 100
    # momentum_candles = 3 (YAML override), default 5
    
    rsi = calculate_rsi(closes, period=14)      # Simple average RSI
    atr_pct = calculate_atr(highs, lows, closes, period=14) / closes[-1] * 100
    adx = calculate_adx(highs, lows, closes, period=14)
    vwap = calculate_vwap(highs, lows, closes, volumes)
    funding = api.get_funding_rate(symbol)[0]["fundingRate"]
    
    # ─── Step 4: Regime Filter ──────────────────────────────
    if regime_filter and adx < adx_trending and not is_new_listing:
        stats.regime_skip += 1
        return None  # Choppy market — don't trade
    # adx_trending = 15 (YAML), default 20
    
    # ─── Step 5: 8-Tier Signal Evaluation ───────────────────
    side = None
    confidence = 0.0
    reason = ""
    
    # ── TIER 1: Volume Spike + Momentum (strongest) ─────────
    if volume_ratio >= volume_spike_mult:  # 2.0x
        if momentum > momentum_threshold:   # +0.08%
            side = "LONG"
            confidence = 0.55 + min(0.15, volume_ratio/20) + min(0.15, momentum/5)
            reason = "VolSpike+Momentum"
        elif momentum < -momentum_threshold: # -0.08%
            side = "SHORT"
            confidence = 0.55 + min(0.15, volume_ratio/20) + min(0.15, abs(momentum)/5)
            reason = "VolSpike+Momentum"
    
    # ── TIER 2: RSI Extreme + Volume ────────────────────────
    if not side and volume_ratio >= volume_spike_mult:
        if rsi < rsi_oversold:  # RSI < 30
            side = "LONG"
            confidence = 0.55 + min(0.15, volume_ratio/20)
            reason = "Oversold+VolSpike"
        elif rsi > rsi_overbought:  # RSI > 70
            side = "SHORT"
            confidence = 0.55 + min(0.15, volume_ratio/20)
            reason = "Overbought+VolSpike"
    
    # ── TIER 3: Funding Rate + Momentum ─────────────────────
    if not side:
        if funding < -0.001 and momentum > momentum_threshold:
            side = "LONG"  # Shorts paying longs → squeeze up
            confidence = 0.55 + min(0.20, abs(funding) * 100)
            reason = "NegFunding+Mom"
        elif funding > 0.001 and momentum < -momentum_threshold:
            side = "SHORT"  # Longs paying shorts → squeeze down
            confidence = 0.55 + min(0.20, abs(funding) * 100)
            reason = "PosFunding+Mom"
    
    # ── TIER 4: New Listing Aggressive ──────────────────────
    if not side and is_new_listing:
        if abs(momentum) > momentum_threshold:
            side = "LONG" if momentum > 0 else "SHORT"
            confidence = 0.56 + min(0.15, abs(momentum) / 2)
            reason = "NewList+Momentum"
        elif volume_ratio >= 1.3 and abs(momentum) > 0.03:
            side = "LONG" if momentum > 0 else "SHORT"
            confidence = 0.56 + min(0.10, abs(momentum) / 3)
            reason = "NewList+WeakVol"
    
    # ── TIER 5: Consecutive Candle Run ──────────────────────
    if not side and volume_ratio >= 1.2:
        consecutive = count_consecutive_candles(klines)
        if consecutive >= 3:
            side = direction_of_run(klines)
            confidence = 0.56 + min(0.10, consecutive * 0.03)
            reason = f"ConsecCandles({consecutive})"
    
    # ── TIER 6: High Volatility Momentum ────────────────────
    if not side and atr_pct > 1.0 and volume_ratio >= 1.1:
        if momentum > momentum_threshold:
            side = "LONG"
            confidence = 0.56 + min(0.10, atr_pct / 5)
            reason = "HighVol+Mom"
        elif momentum < -momentum_threshold:
            side = "SHORT"
            confidence = 0.56 + min(0.10, atr_pct / 5)
            reason = "HighVol+Mom"
    
    # ── TIER 7: Daily Trend Following ───────────────────────
    if not side and abs(price_change_24h) > 5.0 and volume_ratio >= 1.1:
        if price_change_24h > 0 and momentum > momentum_threshold:
            side = "LONG"
            confidence = 0.56 + min(0.15, abs(price_change_24h) / 20)
            reason = "DailyTrend+Mom"
        elif price_change_24h < 0 and momentum < -momentum_threshold:
            side = "SHORT"
            confidence = 0.56 + min(0.15, abs(price_change_24h) / 20)
            reason = "DailyTrend+Mom"
    
    # ── TIER 8: VWAP Reversion + RSI ────────────────────────
    if not side and adx > adx_trending:  # Only in trending markets
        price_vs_vwap = (closes[-1] - vwap) / vwap * 100
        if abs(price_vs_vwap) < 0.3 and 40 < rsi < 60:
            if momentum > momentum_threshold:
                side = "LONG"
                confidence = 0.57 + min(0.10, abs(price_vs_vwap) / 0.1)
                reason = "VWAP+RSI"
            elif momentum < -momentum_threshold:
                side = "SHORT"
                confidence = 0.57 + min(0.10, abs(price_vs_vwap) / 0.1)
                reason = "VWAP+RSI"
    
    # ─── Step 6: Post-processing ────────────────────────────
    if not side:
        return None  # No signal matched
    
    confidence = min(confidence, 0.90)  # Cap at 90%
    if confidence < confidence_threshold:  # 0.54 minimum
        return None  # Too weak
    
    # Mark cooldown
    cooldown[symbol] = time()
    
    return Signal(
        symbol=symbol,
        side=side,
        confidence=confidence,
        entry_price=closes[-1],
        reason=reason,
        volume_ratio=volume_ratio,
        momentum_pct=momentum,
        rsi=rsi,
        funding_rate=funding,
        atr_pct=atr_pct,
    )


# ─── Indicator Calculations ──────────────────────────────────

def calculate_rsi(closes, period=14):
    """Simple average RSI (NOT Wilder's EMA smoothing)."""
    if len(closes) < period + 1:
        return 50.0
    
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def calculate_adx(highs, lows, closes, period=14):
    """Full ADX with Wilder's smoothing.
    +DM/-DM → smoothed +DI/-DI → DX → ADX
    """
    if len(closes) < 2 * period:
        return 0.0
    
    # Calculate +DM, -DM, TR
    plus_dm_list, minus_dm_list, tr_list = [], [], []
    for i in range(1, len(highs)):
        high_diff = highs[i] - highs[i-1]
        low_diff = lows[i-1] - lows[i]
        
        plus_dm = high_diff if high_diff > low_diff and high_diff > 0 else 0
        minus_dm = low_diff if low_diff > high_diff and low_diff > 0 else 0
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        plus_dm_list.append(plus_dm)
        minus_dm_list.append(minus_dm)
        tr_list.append(tr)
    
    # Wilder's smoothing (first value = SMA, subsequent = prev*13/14 + new/14)
    def wilder_smooth(values, period):
        result = [sum(values[:period])]
        for i in range(period, len(values)):
            result.append(result[-1] * (period - 1) / period + values[i])
        return result
    
    smoothed_plus_dm = wilder_smooth(plus_dm_list, period)
    smoothed_minus_dm = wilder_smooth(minus_dm_list, period)
    smoothed_tr = wilder_smooth(tr_list, period)
    
    # +DI, -DI
    plus_di = [smoothed_plus_dm[i] / smoothed_tr[i] * 100 if smoothed_tr[i] > 0 else 0
               for i in range(len(smoothed_tr))]
    minus_di = [smoothed_minus_dm[i] / smoothed_tr[i] * 100 if smoothed_tr[i] > 0 else 0
                for i in range(len(smoothed_tr))]
    
    # DX → ADX
    dx = []
    for i in range(len(plus_di)):
        di_sum = plus_di[i] + minus_di[i]
        if di_sum > 0:
            dx.append(abs(plus_di[i] - minus_di[i]) / di_sum * 100)
        else:
            dx.append(0)
    
    if len(dx) < period:
        return 0.0
    
    # ADX = Wilder's smooth of DX
    adx = sum(dx[:period]) / period
    for i in range(period, len(dx)):
        adx = adx * (period - 1) / period + dx[i] / period
    
    return adx


def calculate_vwap(highs, lows, closes, volumes):
    """Volume-Weighted Average Price over last 60 candles."""
    typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    cumulative_tp_vol = sum(tp * v for tp, v in zip(typical_prices, volumes))
    cumulative_vol = sum(volumes)
    return cumulative_tp_vol / cumulative_vol if cumulative_vol > 0 else closes[-1]
