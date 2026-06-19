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
