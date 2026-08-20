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

# --- Multi-Strategy Presets & Trading Profiles ---
STRATEGY_PROFILES = {
    "all": {
        "id": "all",
        "name_en": "All-Round Confluence",
        "name_zh": "全景多维共振",
        "icon": "layers",
        "desc_en": "Balanced 5-factor scoring model across technicals, fundamentals, sentiment, valuation, and relative strength.",
        "desc_zh": "均衡 5 维共振模型，兼顾技术形态、基本面、市场情绪、估值与相对强度。",
        "dim_caps": {"tech": 30, "fund": 30, "sent": 15, "val": 5, "rs": 20},
        "min_score": 35,
        "min_dimensions": 2,
        "required_factors": [],
    },
    "momentum": {
        "id": "momentum",
        "name_en": "Momentum Alpha",
        "name_zh": "动量主升突破",
        "icon": "zap",
        "desc_en": "Prioritizes high relative strength vs SPY, breakout patterns, unusual volume, and leading sectors.",
        "desc_zh": "聚焦跑赢大盘的相对强度龙头、技术面放量突破及领涨板块主升浪标的。",
        "dim_caps": {"tech": 35, "fund": 10, "sent": 15, "val": 5, "rs": 35},
        "min_score": 38,
        "min_dimensions": 2,
        "required_factors": ["breakout", "breakout_candidate", "volume_spike", "momentum_leader"],
    },
    "compounder": {
        "id": "compounder",
        "name_en": "Quality Compounder",
        "name_zh": "优质价值复利",
        "icon": "gem",
        "desc_en": "High ROE, low debt, reasonable valuation, and pullbacks to moving average support.",
        "desc_zh": "精选高 ROE、低负债、估值合理且回踩关键均线支撑的绩优核心资产。",
        "dim_caps": {"tech": 15, "fund": 45, "sent": 10, "val": 15, "rs": 15},
        "min_score": 35,
        "min_dimensions": 2,
        "required_factors": ["quality_compounder", "insider_buying", "pullback"],
    },
    "squeeze": {
        "id": "squeeze",
        "name_en": "Short Squeeze Play",
        "name_zh": "逼空爆发狙击",
        "icon": "flame",
        "desc_en": "High short float (>15%), sudden volume spikes, and retail sentiment surges for explosive moves.",
        "desc_zh": "锁定高卖空比例、异常放量异动与散户热度激增的爆发性逼空博弈机会。",
        "dim_caps": {"tech": 25, "fund": 10, "sent": 40, "val": 5, "rs": 20},
        "min_score": 35,
        "min_dimensions": 2,
        "required_factors": ["short_squeeze", "volume_spike", "reddit_popular"],
    },
    "reversal": {
        "id": "reversal",
        "name_en": "Oversold Bounce",
        "name_zh": "深跌超卖筑底",
        "icon": "shield",
        "desc_en": "Deep RSI oversold levels, double bottoms, and executive insider accumulation at support.",
        "desc_zh": "捕捉 RSI 深度超卖、双底筑底以及高管内部人抄底增持的左侧/右侧反弹机会。",
        "dim_caps": {"tech": 40, "fund": 25, "sent": 10, "val": 15, "rs": 10},
        "min_score": 35,
        "min_dimensions": 2,
        "required_factors": ["reversal", "insider_buying"],
    },
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
    28,  # Institutional Ownership
    29,  # Institutional Transactions
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

# Dedicated institutional screener columns
INSTITUTIONAL_COLUMNS = [
    0,   # No.
    1,   # Ticker
    2,   # Company
    3,   # Sector
    4,   # Industry
    6,   # Market Cap.
    28,  # Institutional Ownership
    29,  # Institutional Transactions
    64,  # Relative Volume
    65,  # Price
    66,  # Change
    67,  # Volume
]

INSTITUTIONAL_FILTERS = {
    "accumulation": {
        "InstitutionalTransactions": "Over +5%",
    },
    "high_ownership": {
        "InstitutionalOwnership": "Over 70%",
    },
    "distribution": {
        "InstitutionalTransactions": "Under -5%",
    },
}

# Curated 13F Super Investors & Top Fund Portfolios
SUPER_INVESTORS_DATA = {
    "berkshire": {
        "id": "berkshire",
        "manager_en": "Warren Buffett",
        "manager_zh": "沃伦·巴菲特",
        "fund_name_en": "Berkshire Hathaway",
        "fund_name_zh": "伯克希尔·哈撒韦",
        "avatar": "🪙",
        "portfolio_value": "$295B",
        "top_holdings_count": 10,
        "style_en": "Deep Value & Durable Moats",
        "style_zh": "深度价值与护城河复利",
        "holdings": [
            {"ticker": "AAPL", "company": "Apple Inc.", "weight": "24.5%", "shares": "300.0M", "value": "$68.2B", "action": "hold", "sector": "Technology"},
            {"ticker": "AXP", "company": "American Express", "weight": "15.2%", "shares": "151.6M", "value": "$42.3B", "action": "hold", "sector": "Financial"},
            {"ticker": "BAC", "company": "Bank of America", "weight": "11.1%", "shares": "680.2M", "value": "$30.8B", "action": "reduce", "sector": "Financial"},
            {"ticker": "KO", "company": "Coca-Cola Co", "weight": "9.8%", "shares": "400.0M", "value": "$27.4B", "action": "hold", "sector": "Consumer Defensive"},
            {"ticker": "CVX", "company": "Chevron Corp", "weight": "6.2%", "shares": "118.6M", "value": "$17.3B", "action": "hold", "sector": "Energy"},
            {"ticker": "OXY", "company": "Occidental Petroleum", "weight": "4.8%", "shares": "255.3M", "value": "$13.4B", "action": "buy", "sector": "Energy"},
            {"ticker": "MCO", "company": "Moody's Corp", "weight": "4.1%", "shares": "24.7M", "value": "$11.5B", "action": "hold", "sector": "Financial"},
            {"ticker": "KHC", "company": "Kraft Heinz Co", "weight": "3.5%", "shares": "325.6M", "value": "$9.8B", "action": "hold", "sector": "Consumer Defensive"},
            {"ticker": "CB", "company": "Chubb Limited", "weight": "2.8%", "shares": "27.0M", "value": "$7.8B", "action": "buy", "sector": "Financial"},
            {"ticker": "DVA", "company": "DaVita Inc", "weight": "1.9%", "shares": "36.1M", "value": "$5.3B", "action": "hold", "sector": "Healthcare"}
        ]
    },
    "bridgewater": {
        "id": "bridgewater",
        "manager_en": "Ray Dalio",
        "manager_zh": "瑞·达利欧",
        "fund_name_en": "Bridgewater Associates",
        "fund_name_zh": "桥水基金",
        "avatar": "🌊",
        "portfolio_value": "$19.8B",
        "top_holdings_count": 10,
        "style_en": "All-Weather Macro Parity",
        "style_zh": "全天候全资产宏观对冲",
        "holdings": [
            {"ticker": "IVV", "company": "iShares Core S&P 500 ETF", "weight": "6.2%", "shares": "2.1M", "value": "$1.23B", "action": "buy", "sector": "ETF"},
            {"ticker": "IEMG", "company": "iShares Core MSCI Emerging", "weight": "5.4%", "shares": "18.5M", "value": "$1.07B", "action": "buy", "sector": "ETF"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "4.8%", "shares": "5.2M", "value": "$950M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "4.3%", "shares": "6.5M", "value": "$850M", "action": "reduce", "sector": "Technology"},
            {"ticker": "META", "company": "Meta Platforms Inc", "weight": "3.9%", "shares": "1.4M", "value": "$770M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "3.5%", "shares": "1.6M", "value": "$690M", "action": "hold", "sector": "Technology"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "3.1%", "shares": "3.2M", "value": "$615M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "PG", "company": "Procter & Gamble Co", "weight": "2.8%", "shares": "3.3M", "value": "$550M", "action": "hold", "sector": "Consumer Defensive"},
            {"ticker": "JNJ", "company": "Johnson & Johnson", "weight": "2.4%", "shares": "2.9M", "value": "$475M", "action": "reduce", "sector": "Healthcare"},
            {"ticker": "COST", "company": "Costco Wholesale Corp", "weight": "2.1%", "shares": "450K", "value": "$415M", "action": "buy", "sector": "Consumer Defensive"}
        ]
    },
    "renaissance": {
        "id": "renaissance",
        "manager_en": "Jim Simons / Peter Brown",
        "manager_zh": "量化之王·复兴科技",
        "fund_name_en": "Renaissance Technologies",
        "fund_name_zh": "复兴科技 (大奖章)",
        "avatar": "⚡",
        "portfolio_value": "$62.4B",
        "top_holdings_count": 10,
        "style_en": "Quantitative Statistical Arbitrage",
        "style_zh": "高胜率数理统计套利与 Alpha",
        "holdings": [
            {"ticker": "PLTR", "company": "Palantir Technologies", "weight": "2.8%", "shares": "38.2M", "value": "$1.75B", "action": "buy", "sector": "Technology"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "2.5%", "shares": "12.0M", "value": "$1.56B", "action": "buy", "sector": "Technology"},
            {"ticker": "AAPL", "company": "Apple Inc.", "weight": "2.2%", "shares": "6.1M", "value": "$1.37B", "action": "hold", "sector": "Technology"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "2.0%", "shares": "6.5M", "value": "$1.25B", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "META", "company": "Meta Platforms Inc", "weight": "1.9%", "shares": "2.1M", "value": "$1.18B", "action": "reduce", "sector": "Communication Services"},
            {"ticker": "TSLA", "company": "Tesla Inc", "weight": "1.7%", "shares": "4.8M", "value": "$1.06B", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "AVGO", "company": "Broadcom Inc", "weight": "1.6%", "shares": "5.9M", "value": "$1.00B", "action": "buy", "sector": "Technology"},
            {"ticker": "TSM", "company": "Taiwan Semiconductor", "weight": "1.5%", "shares": "5.1M", "value": "$935M", "action": "buy", "sector": "Technology"},
            {"ticker": "LLY", "company": "Eli Lilly and Co", "weight": "1.4%", "shares": "1.1M", "value": "$870M", "action": "reduce", "sector": "Healthcare"},
            {"ticker": "NVO", "company": "Novo Nordisk A/S", "weight": "1.3%", "shares": "7.5M", "value": "$810M", "action": "hold", "sector": "Healthcare"}
        ]
    },
    "pershing": {
        "id": "pershing",
        "manager_en": "Bill Ackman",
        "manager_zh": "比尔·阿克曼",
        "fund_name_en": "Pershing Square Capital",
        "fund_name_zh": "潘兴广场资本",
        "avatar": "🎯",
        "portfolio_value": "$13.2B",
        "top_holdings_count": 8,
        "style_en": "Concentrated High-Conviction Value",
        "style_zh": "极度集中高确信度商业特权股",
        "holdings": [
            {"ticker": "HLT", "company": "Hilton Worldwide", "weight": "18.5%", "shares": "9.8M", "value": "$2.44B", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "CMG", "company": "Chipotle Mexican Grill", "weight": "16.8%", "shares": "35.2M", "value": "$2.22B", "action": "reduce", "sector": "Consumer Cyclical"},
            {"ticker": "QSR", "company": "Restaurant Brands Intl", "weight": "15.4%", "shares": "28.5M", "value": "$2.03B", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "13.2%", "shares": "9.5M", "value": "$1.74B", "action": "hold", "sector": "Communication Services"},
            {"ticker": "GOOG", "company": "Alphabet Inc Class C", "weight": "10.5%", "shares": "7.4M", "value": "$1.39B", "action": "hold", "sector": "Communication Services"},
            {"ticker": "NKE", "company": "Nike Inc", "weight": "9.8%", "shares": "16.3M", "value": "$1.29B", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "BAM", "company": "Brookfield Asset Mgmt", "weight": "8.5%", "shares": "19.5M", "value": "$1.12B", "action": "new", "sector": "Financial"},
            {"ticker": "SEAS", "company": "United Parks & Resorts", "weight": "5.2%", "shares": "12.8M", "value": "$685M", "action": "hold", "sector": "Consumer Cyclical"}
        ]
    },
    "appaloosa": {
        "id": "appaloosa",
        "manager_en": "David Tepper",
        "manager_zh": "大卫·泰珀",
        "fund_name_en": "Appaloosa Management",
        "fund_name_zh": "阿帕卢萨资产",
        "avatar": "🐅",
        "portfolio_value": "$6.7B",
        "top_holdings_count": 10,
        "style_en": "Distressed Assets & Tech Bet",
        "style_zh": "困境反转大周期与科技核心重仓",
        "holdings": [
            {"ticker": "BABA", "company": "Alibaba Group Holding", "weight": "12.8%", "shares": "9.5M", "value": "$855M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "PDD", "company": "PDD Holdings Inc", "weight": "10.2%", "shares": "5.8M", "value": "$685M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "8.5%", "shares": "2.9M", "value": "$570M", "action": "reduce", "sector": "Consumer Cyclical"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "7.4%", "shares": "1.2M", "value": "$495M", "action": "hold", "sector": "Technology"},
            {"ticker": "META", "company": "Meta Platforms Inc", "weight": "6.8%", "shares": "810K", "value": "$455M", "action": "reduce", "sector": "Communication Services"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "5.9%", "shares": "2.1M", "value": "$395M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "5.2%", "shares": "2.7M", "value": "$350M", "action": "reduce", "sector": "Technology"},
            {"ticker": "BIDU", "company": "Baidu Inc", "weight": "4.8%", "shares": "3.5M", "value": "$320M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "JD", "company": "JD.com Inc", "weight": "4.2%", "shares": "7.8M", "value": "$280M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "INTC", "company": "Intel Corporation", "weight": "3.5%", "shares": "10.5M", "value": "$235M", "action": "new", "sector": "Technology"}
        ]
    },
    "greenwoods": {
        "id": "greenwoods",
        "manager_en": "George Jiang",
        "manager_zh": "蒋锦志 / 景林资产",
        "fund_name_en": "Greenwoods Asset Management",
        "fund_name_zh": "景林资产 (顶级中资美股)",
        "avatar": "🌲",
        "portfolio_value": "$3.8B",
        "top_holdings_count": 10,
        "style_en": "Global Chinese Alpha & AI Giants",
        "style_zh": "中国出海龙头与全球 AI 基础设施",
        "holdings": [
            {"ticker": "PDD", "company": "PDD Holdings Inc", "weight": "19.5%", "shares": "6.2M", "value": "$740M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "META", "company": "Meta Platforms Inc", "weight": "16.2%", "shares": "1.1M", "value": "$615M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "TSM", "company": "Taiwan Semiconductor", "weight": "12.8%", "shares": "2.6M", "value": "$485M", "action": "buy", "sector": "Technology"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "10.4%", "shares": "3.0M", "value": "$395M", "action": "buy", "sector": "Technology"},
            {"ticker": "NET", "company": "Cloudflare Inc", "weight": "6.8%", "shares": "2.5M", "value": "$260M", "action": "new", "sector": "Technology"},
            {"ticker": "BABA", "company": "Alibaba Group Holding", "weight": "6.2%", "shares": "2.4M", "value": "$235M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "5.5%", "shares": "500K", "value": "$210M", "action": "hold", "sector": "Technology"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "4.8%", "shares": "950K", "value": "$182M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "FUTU", "company": "Futu Holdings Ltd", "weight": "4.1%", "shares": "1.8M", "value": "$155M", "action": "buy", "sector": "Financial"},
            {"ticker": "DOX", "company": "Amdocs Limited", "weight": "3.2%", "shares": "1.4M", "value": "$122M", "action": "hold", "sector": "Technology"}
        ]
    }
}

def apply_signal_filter(fcustom, sig_key, sig_val):
    if sig_key in CUSTOM_FILTERS:
        fcustom.set_filter(filters_dict=CUSTOM_FILTERS[sig_key])
    else:
        fcustom.set_filter(signal=sig_val)


