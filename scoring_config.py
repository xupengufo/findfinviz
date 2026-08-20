"""
Scoring configuration for the Confluence engine (P0-1).

All dimension weights, factor scores, and thresholds live here so they can be
tuned without hunting through get_confluences(). The 5-dimension model replaces
the old 4-dimension (35/35/20/10) model:

    Technical Structure  : 30  (was 35)
    Fundamentals         : 30  (was 35)
    Market Sentiment     : 15  (was 20)
    Valuation            :  5  (was 10 — minimal weight for short-term trading)
    Relative Strength    : 20  (NEW — excess return vs SPY, the active trader's edge)

Total = 100
"""

# Dimension caps (must sum to 100)
DIMENSION_CAPS = {
    "tech": 30,
    "fund": 30,
    "sent": 15,
    "val": 5,
    "rs": 20,
}

# --- Technical Structure factor scores ---
TECH_FACTORS = {
    "reversal": 17,           # was 20, scaled for 30 cap
    "pullback": 15,           # was 18
    "breakout": 13,           # was 15
    "breakout_candidate": 15, # was 18
    "confirm_bonus_per": 4,   # +4 per additional pattern
    "confirm_bonus_cap": 8,   # max confirmation bonus
    "volume_spike": 4,        # was 5
    "high_volatility": 2,
    "strong_sector": 3,
    "conflict_overbought_reversal": -8,  # was -10
    "conflict_reversal_bearish": -8,     # was -10
}

# --- Fundamentals & Insiders factor scores ---
FUND_FACTORS = {
    "insider_buying": 13,       # was 15
    "quality_compounder": 13,   # was 15
    "analyst_upgrade": 8,       # was 10
    "earnings_catalyst": 4,     # was 5
    "analyst_downgrade": -8,    # was -10
}

# --- Market Sentiment & Flow factor scores ---
SENT_FACTORS = {
    "momentum_leader": 8,       # was 10
    "reddit_popular": 4,        # was 5
    "short_squeeze_combined": 6, # was 8
    "short_squeeze_alone": 2,    # was 3
    "bearish_momentum": -4,      # was -5
}

# --- Valuation factor thresholds (max 5) ---
VALUATION = {
    "fwd_pe_undervalued": (0, 15, 3),    # (low, high, score)
    "fwd_pe_fair": (15, 25, 2),
    "fwd_pe_high_ok": (25, 40, 1),
    "peg_undervalued": (0, 1.0, 2),
    "peg_fair": (1.0, 2.0, 1),
    "peg_expensive": (2.0, 3.0, 0),
}

# --- Relative Strength scoring (max 20) ---
# Based on excess return vs SPY over 5d / 20d / ~60d windows.
# FinViz Perf Week ≈ 5d, Perf Month ≈ 20d, Perf Quarter ≈ 60d.
RS_SCORING = {
    "all_three_positive_and_rising": 20,  # strongest RS — true market leader
    "two_of_three_positive": 12,
    "one_of_three_positive": 5,
    "none_positive": 0,                    # weak — lagging the market
}

# Minimum score and dimension count for a ticker to qualify as a confluence
MIN_SCORE = 35
MIN_DIMENSIONS = 2

# Liquidity threshold for ADTV (Average Daily Trading Value) flagging
LIQUIDITY_FLOOR = 5_000_000  # $5M

# Supported FinViz signals mapping
SUPPORTED_SIGNALS = {
    "oversold": "Oversold",
    "overbought": "Overbought",
    "double_bottom": "Double Bottom",
    "wedge_up": "Wedge Up",
    "wedge_down": "Wedge Down",
    "triangle_ascending": "Triangle Ascending",
    "top_gainers": "Top Gainers",
    "top_losers": "Top Losers",
    "new_high": "New High",
    "most_active": "Most Active",
    "most_volatile": "Most Volatile",
    "unusual_volume": "Unusual Volume",
    "upgrades": "Upgrades",
    "downgrades": "Downgrades",
    "earnings_before": "Earnings Before",
    "earnings_after": "Earnings After",
    "recent_insider_buying": "Recent Insider Buying",
    "high_short_interest": "high_short_interest",
    "pullback": "pullback",
    "breakout_candidate": "breakout_candidate",
    "quality_compounder": "quality_compounder"
}

CUSTOM_FILTERS = {
    # Squeeze setup: high short interest + volume spark to ignite
    "high_short_interest": {
        "Float Short": "Over 15%",
        "Relative Volume": "Over 1.5"
    },
    # Pullback in an uptrend: above 50/200 SMA (trend up) but pulled back
    # below 20-day SMA with RSI cooling (<50).
    "pullback": {
        "50-Day Simple Moving Average": "Price above SMA50",
        "200-Day Simple Moving Average": "Price above SMA200",
        "20-Day Simple Moving Average": "Price below SMA20",
        "RSI (14)": "Not Overbought (<50)"
    },
    # Breakout candidate: near 52w high + strong volume (>=2x) + uptrend confirmed
    "breakout_candidate": {
        "52-Week High/Low": "0-5% below High",
        "Relative Volume": "Over 2",
        "50-Day Simple Moving Average": "Price above SMA50"
    },
    # Quality compounder: strong fundamentals AND in a long-term uptrend
    "quality_compounder": {
        "Return on Equity": "Over +20%",
        "Debt/Equity": "Under 0.5",
        "EPS growththis year": "Over 10%",
        "Gross Margin": "Positive (>0%)",
        "P/E": "Profitable (>0)",
        "200-Day Simple Moving Average": "Price above SMA200"
    }
}

# FinViz screener column indices (see finvizfinance/constants.py CUSTOM_SCREENER_COLUMNS).
SCREENER_COLUMNS = [
    0,   # No.
    1,   # Ticker
    2,   # Company
    3,   # Sector
    4,   # Industry
    6,   # Market Cap.
    7,   # P/E
    8,   # Forward P/E
    9,   # PEG
    13,  # P/Free Cash Flow
    30,  # Float Short
    33,  # Return on Equity
    38,  # Total Debt/Equity
    42,  # Performance (Week)  ~ 5-day return - used for TechScore momentum + RS
    43,  # Performance (Month) ~ 20-day return - used for TechScore momentum + RS
    44,  # Performance (Quarter) ~ 60-day return - used for RS
    49,  # Average True Range (ATR)
    52,  # 20-Day Simple Moving Average
    53,  # 50-Day Simple Moving Average
    54,  # 200-Day Simple Moving Average
    57,  # 52-Week High
    63,  # Average Volume       - used for ADTV (liquidity) filtering
    64,  # Relative Volume
    65,  # Price
    66,  # Change
    67,  # Volume
    68,  # Earnings Date
    69,  # Target Price
]

def apply_signal_filter(fcustom, sig_key, sig_val):
    if sig_key in CUSTOM_FILTERS:
        fcustom.set_filter(filters_dict=CUSTOM_FILTERS[sig_key])
    else:
        fcustom.set_filter(signal=sig_val)

