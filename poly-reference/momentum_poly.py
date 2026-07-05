"""
PolyClaw-Cipher v3 — Momentum Strategy (Original Polymarket Version)
====================================================================
Ported to Hyperliquid as MomentumHLStrategy v1, then evolved to v2.
This is the ORIGINAL v1 port that directly documents Polymarket -> Crypto diffs.

The Polymarket bot (Paper Fifteen) used this strategy on binary outcome
markets (YES/NO tokens priced $0-$1). The crypto bot (Binance meme scalp)
uses a completely different 8-tier signal system.

KEY COMPARISON: How does Fifteen's simple momentum beat our 8-tier system?
"""

class MomentumHLStrategy(BaseStrategy):
    """Hyperliquid momentum -- adapted from PolyClaw-Cipher v3."""

    name = "momentum"

    def __init__(self, config):
        # --- Timeframe ---
        # v1 (Fifteen-style): lookback 60s/300s, EMA-30/120 on tick stream
        # v2 (crypto-tuned): EMA-9/21 on 1-min CANDLES, lookback 120s/600s
        self.lookback_short_sec = config.get("lookback_short_sec", 60)   # v1: 60, v2: 120
        self.lookback_long_sec = config.get("lookback_long_sec", 300)    # v1: 300, v2: 600
        self.ema_short_period = config.get("ema_short_period", 30)       # v1: 30, v2: 9
        self.ema_long_period = config.get("ema_long_period", 120)        # v1: 120, v2: 21

        # --- Momentum Thresholds ---
        # v1: ultra-sensitive (0.002% / 0.005%) -- catches micro-moves
        # v2: higher (0.05% / 0.10%) -- filters noise on 1m candles
        # Binance bot: 0.08% on 1m candles (medium sensitivity)
        self.min_momentum_short_pct = config.get("min_momentum_short_pct", 0.002)  # v1
        self.min_momentum_long_pct = config.get("min_momentum_long_pct", 0.005)    # v1

        # --- Exit Parameters ---
        # Fifteen (Polymarket): TP 8%, SL 7.6%, no trailing -- WIDE stops
        #   Why wide? PM fees = 25bps round-trip, need big moves to profit
        #   Result: low win rate (~40%) but big wins when right
        # v1 (Hyperliquid): TP 8%, SL 7.6% -- same as Fifteen initially
        # v2 (Hyperliquid): TP 1.2%, SL 0.8%, trail 0.5% -- TIGHT stops
        #   Why tight? HL fees = 7bps, can profit on small moves
        # Binance bot: TP 1.0%, SL 0.5%, trail 0.25% -- TIGHTEST
        #   Binance fees = 10bps round-trip, meme spread adds 12-25bps
        self.take_profit_pct = config.get("take_profit_pct", 8.0)      # v1: 8.0, v2: 1.2
        self.stop_loss_pct = config.get("stop_loss_pct", 7.6)          # v1: 7.6, v2: 0.8
        self.max_hold_sec = config.get("max_hold_sec", 300)
        self.trailing_stop_pct = config.get("trailing_stop_pct", 0.0)   # v1: disabled, v2: 0.5

        # --- Position Limits ---
        # Fifteen: max 4 positions, $6 cap (1.2x $5 bankroll), 15s cooldown
        # Binance bot: max 5 positions, 20% equity sizing, 15s cooldown
        self.max_positions = config.get("max_positions", 4)
        self.max_notional_per_trade = config.get("max_notional_per_trade", 8.4)
        self.cooldown_sec = config.get("cooldown_sec", 15)
        self.max_pct_per_trade = config.get("max_pct_per_trade", 0.10)

        # --- Leverage ---
        # Fifteen (PM): No leverage (binary outcome, max loss = investment)
        # v1 (HL): 5x leverage
        # Binance bot: 20x leverage
        self.leverage = config.get("leverage", 5)

        # --- Fees ---
        # Polymarket: 25bps round-trip (maker 0bps + taker 25bps one-side)
        # Hyperliquid: 7bps round-trip (3.5bps per side)
        # Binance USDM: 10bps round-trip (5bps taker per side) + spread
        self.fee_bps = config.get("fee_bps", 3.5)
        self.round_trip_fee = self.fee_bps * 2

    async def evaluate(self, market, context):
        """Core signal logic -- simple EMA + ROC momentum."""

        coin = market.coin
        mid = self._feed.get_mid(coin)

        # -- Filters --
        spread = self._feed.get_spread_bps(coin)
        if spread > self.max_spread_bps:
            return None  # Skip illiquid

        if market.vol_24h < self.min_volume_24h:
            return None  # Skip low volume

        # -- Momentum Calculation --
        roc_short = self._feed.get_roc(coin, self.lookback_short_sec)
        roc_long = self._feed.get_roc(coin, self.lookback_long_sec)
        ema_short = self._feed.get_ema(coin, self.ema_short_period)
        ema_long = self._feed.get_ema(coin, self.ema_long_period)

        # Direction: ROC primary, EMA confirmation
        if roc_short > 0:
            side = Side.LONG
        elif roc_short < 0:
            side = Side.SHORT
        else:
            if ema_short > ema_long:
                side = Side.LONG
            elif ema_short < ema_long:
                side = Side.SHORT
            else:
                return None

        # -- Confidence Scoring (3 factors only) --
        # v1: momentum(40%) + trend(40%) + spread(20%)
        # v2: momentum(35%) + trend(30%) + RSI(20%) + spread(15%)
        # Binance bot: 8-tier cascading with different formulas per tier

        momentum_score = min(1.0, abs(roc_short) / (self.min_momentum_short_pct * 5))
        ema_agrees = (side == Side.LONG and ema_short > ema_long) or \
                     (side == Side.SHORT and ema_short < ema_long)
        trend_aligns = (side == Side.LONG and roc_long > 0) or \
                       (side == Side.SHORT and roc_long < 0)

        if ema_agrees and trend_aligns:
            trend_score = 1.0
        elif ema_agrees or trend_aligns:
            trend_score = 0.7
        else:
            trend_score = 0.4

        spread_score = max(0.0, 1.0 - spread / self.max_spread_bps)

        confidence = 0.4 * momentum_score + 0.4 * trend_score + 0.2 * spread_score

        if confidence < self.min_confidence:  # v1: 0.25, v2: 0.60
            return None

        # -- Sizing --
        bankroll = context.get("bankroll", 1000.0)
        margin_usd = bankroll * self.max_pct_per_trade * confidence
        notional_usd = min(margin_usd * self.leverage, self.max_notional_per_trade)

        return Signal(coin=coin, side=side, price=mid,
                     size_usd=round(notional_usd, 2),
                     confidence=confidence, reason="EMA+ROC momentum")


# ====================================================================
# KEY STRUCTURAL DIFFERENCES: Fifteen vs Binance Meme Scalp
# ====================================================================
#
# 1. SIGNAL ARCHITECTURE
#    Fifteen:  ONE signal type (EMA+ROC momentum). Simple, focused.
#    Binance:  EIGHT signal tiers. Complex, broad. First-match-wins.
#    Question: Does more tiers = more edge, or more noise?
#
# 2. ENTRY SENSITIVITY
#    Fifteen:  min_momentum 0.002% (ultra-sensitive, catches micro-moves)
#    Binance:  min_momentum 0.08% (40x less sensitive)
#    Question: Are we missing profitable micro-moves, or filtering noise?
#
# 3. STOP/TAKE PROFIT WIDTH
#    Fifteen:  TP 8% / SL 7.6% -- very wide. Survives noise. Low win rate but big wins.
#    Binance:  TP 1.0% / SL 0.5% -- very tight. High win rate needed but small wins.
#    Question: Which R:R profile actually works better for meme coins?
#
# 4. FEES & SPREAD
#    Fifteen:  25bps PM round-trip, but NO spread (CLOB market orders)
#    Binance:  10bps fee + 12-25bps spread = 22-35bps round-trip on memes
#    Question: Are meme coins even tradeable with tight stops given real spread cost?
#
# 5. LEVERAGE
#    Fifteen:  No leverage (binary outcome, max loss = 100% of position)
#    Binance:  20x leverage (amplifies both gains AND fee impact)
#    Question: Is 20x leverage making fees eat our edge?
#
# 6. CONFIDENCE SCORING
#    Fifteen:  3 factors (momentum + trend + spread), simple weighted sum
#    Binance:  Per-tier formulas with different adders, caps at 0.90
#    Question: Does the complexity add signal quality or just overfit?
#
# 7. MARKET SELECTION
#    Fifteen:  Pre-selected PM markets, manual or category-based
#    Binance:  Auto-scan 573+ perpetuals, score by volume/volatility/new-listing
#    Question: Are we trading too many marginal markets?
