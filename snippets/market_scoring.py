"""
Market Opportunity Scoring Algorithm
=====================================
Pseudocode extracted from BinanceFuturesScanner._score_market()

Ranks all ~200 Binance USDM perpetual markets to find
the best opportunities for scalping.
"""

def score_market(market_info) -> ScannedMarket:
    """Calculate opportunity score for a single market."""
    
    # ─── Volume Score (0-30) ────────────────────────────────
    # Logarithmic scale: $5M → 5pts, $50M → 15pts, $500M → 30pts
    if market_info.quote_volume_24h > 0:
        volume_score = min(30, max(0, 
            5 + 5 * math.log10(market_info.quote_volume_24h / 5_000_000)
        ))
    else:
        volume_score = 0
    
    # ─── Volatility Score (0-30) ────────────────────────────
    # Linear scale: 2% change → 4pts, 10% → 20pts, 15%+ → 30pts
    volatility_score = min(30, max(0, abs(market_info.price_change_24h) * 2))
    
    # ─── New Listing Score (0-50) ───────────────────────────
    # Decaying bonus based on listing age
    listing_age_days = market_info.listing_age_days
    
    if listing_age_days <= 1:
        new_listing_score = 50.0   # Full bonus — day 1 hype
    elif listing_age_days <= 3:
        new_listing_score = 40.0   # 80% — still fresh
    elif listing_age_days <= 7:
        new_listing_score = 25.0   # 50% — settling
    elif listing_age_days <= 14:
        new_listing_score = 10.0   # 20% — matured
    else:
        new_listing_score = 0.0    # No bonus — established coin
    
    # ─── Total Score ────────────────────────────────────────
    total_score = volume_score + volatility_score + new_listing_score
    # Maximum possible: 30 + 30 + 50 = 110
    
    return ScannedMarket(
        symbol=market_info.symbol,
        volume_score=volume_score,
        volatility_score=volatility_score,
        new_listing_score=new_listing_score,
        total_score=total_score,
        is_new_listing=(listing_age_days <= 14),
        # ... other fields
    )


def scan_all_markets() -> ScanResult:
    """Full market scan pipeline — runs every 5 minutes."""
    
    # Step 1: Get all perpetual symbols
    all_symbols = api.get_perpetual_symbols()
    
    # Step 2: Get 24h tickers (one API call for all)
    tickers = api.get_24h_tickers()
    ticker_map = {t["symbol"]: t for t in tickers}
    
    # Step 3: Get funding rates
    mark_prices = api.get_mark_price()
    funding_map = {m["symbol"]: m for m in mark_prices}
    
    # Step 4: Filter and score
    scored_markets = []
    for symbol_info in all_symbols:
        ticker = ticker_map.get(symbol_info["symbol"])
        if not ticker:
            continue
        
        # Apply filters
        quote_vol = float(ticker.get("quoteVolume", 0))
        price_change = float(ticker.get("priceChangePercent", 0))
        listing_age = calculate_listing_age(symbol_info)
        is_new = listing_age <= 14
        
        # Minimum volume filter ($5M)
        if quote_vol < 5_000_000 and not is_new:
            continue
        
        # Minimum volatility filter (2% 24h change)
        if abs(price_change) < 2.0 and not is_new:
            continue  # New listings exempt from this filter
        
        # Score the market
        market = score_market(...)
        scored_markets.append(market)
    
    # Step 5: Sort by score, take top 30
    scored_markets.sort(key=lambda m: m.total_score, reverse=True)
    top_markets = scored_markets[:30]
    
    return ScanResult(
        total_markets=len(all_symbols),
        filtered_markets=len(scored_markets),
        new_listings=sum(1 for m in scored_markets if m.is_new_listing),
        top_markets=top_markets,
        all_markets=scored_markets,
    )


# ─── Scoring Examples ────────────────────────────────────────
#
# PEPEUSDT (hot meme, $800M vol, +12%, 2 days old):
#   volume: min(30, 5 + 5*log10(800M/5M)) = min(30, 5+5*2.2) = 16
#   volatility: min(30, 12*2) = 24
#   new_listing: 40 (≤3 days)
#   TOTAL: 16 + 24 + 40 = 80 ← very high
#
# BTCUSDT (major, $20B vol, +2.5%, old):
#   volume: min(30, 5 + 5*log10(20B/5M)) = min(30, 5+5*3.6) = 23
#   volatility: min(30, 2.5*2) = 5
#   new_listing: 0
#   TOTAL: 23 + 5 + 0 = 28 ← moderate
#
# RANDOMUSDT (small cap, $3M vol, +1.5%, old):
#   FILTERED OUT — below $5M volume AND below 2% change
