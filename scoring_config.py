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
    },
    "himalaya": {
        "id": "himalaya",
        "manager_en": "Li Lu",
        "manager_zh": "李录 / 喜马拉雅资本",
        "fund_name_en": "Himalaya Capital Management",
        "fund_name_zh": "喜马拉雅资本 (查理·芒格家族基金)",
        "avatar": "🏔️",
        "portfolio_value": "$2.4B",
        "top_holdings_count": 6,
        "style_en": "Deep Value & Munger Discipleship",
        "style_zh": "芒格正统价值投资与长期复利",
        "holdings": [
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "32.5%", "shares": "4.2M", "value": "$780M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "GOOG", "company": "Alphabet Inc Class C", "weight": "26.2%", "shares": "3.4M", "value": "$630M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "BAC", "company": "Bank of America", "weight": "18.5%", "shares": "9.8M", "value": "$445M", "action": "hold", "sector": "Financial"},
            {"ticker": "BRK.B", "company": "Berkshire Hathaway Class B", "weight": "12.4%", "shares": "650K", "value": "$298M", "action": "hold", "sector": "Financial"},
            {"ticker": "EWBC", "company": "East West Bancorp", "weight": "6.8%", "shares": "1.7M", "value": "$163M", "action": "hold", "sector": "Financial"},
            {"ticker": "AAPL", "company": "Apple Inc", "weight": "3.6%", "shares": "380K", "value": "$86M", "action": "buy", "sector": "Technology"}
        ]
    },
    "duanyongping": {
        "id": "duanyongping",
        "manager_en": "Duan Yongping",
        "manager_zh": "段永平 / 大道投资",
        "fund_name_en": "H&H International Investment",
        "fund_name_zh": "H&H 国际投资 (大道无形我有形)",
        "avatar": "💡",
        "portfolio_value": "$14.8B",
        "top_holdings_count": 8,
        "style_en": "Business Model Moats & Concentration",
        "style_zh": "长坡厚雪商业模式与超级集中",
        "holdings": [
            {"ticker": "AAPL", "company": "Apple Inc", "weight": "68.2%", "shares": "44.5M", "value": "$10.1B", "action": "hold", "sector": "Technology"},
            {"ticker": "BRK.B", "company": "Berkshire Hathaway Class B", "weight": "14.5%", "shares": "4.7M", "value": "$2.15B", "action": "hold", "sector": "Financial"},
            {"ticker": "PDD", "company": "PDD Holdings Inc", "weight": "5.8%", "shares": "7.2M", "value": "$860M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "4.2%", "shares": "3.4M", "value": "$620M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "TCEHY", "company": "Tencent Holdings ADR", "weight": "3.1%", "shares": "9.5M", "value": "$460M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "DIS", "company": "Walt Disney Co", "weight": "1.8%", "shares": "2.4M", "value": "$265M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "OXY", "company": "Occidental Petroleum", "weight": "1.2%", "shares": "3.4M", "value": "$180M", "action": "hold", "sector": "Energy"},
            {"ticker": "BABA", "company": "Alibaba Group Holding", "weight": "1.2%", "shares": "1.8M", "value": "$175M", "action": "buy", "sector": "Consumer Cyclical"}
        ]
    },
    "hillhouse": {
        "id": "hillhouse",
        "manager_en": "Zhang Lei",
        "manager_zh": "张磊 / 高瓴资本",
        "fund_name_en": "HHLR Advisors (Hillhouse)",
        "fund_name_zh": "高瓴资本 HHLR (重仓中概与硬科技)",
        "avatar": "🦅",
        "portfolio_value": "$4.5B",
        "top_holdings_count": 10,
        "style_en": "Long-Term Value & Healthcare Tech",
        "style_zh": "长期主义价值投资与生命科技",
        "holdings": [
            {"ticker": "PDD", "company": "PDD Holdings Inc", "weight": "22.8%", "shares": "8.5M", "value": "$1.02B", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "BABA", "company": "Alibaba Group Holding", "weight": "15.4%", "shares": "7.1M", "value": "$690M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "BEKE", "company": "KE Holdings Inc (贝壳)", "weight": "10.2%", "shares": "23.5M", "value": "$460M", "action": "buy", "sector": "Real Estate"},
            {"ticker": "NTES", "company": "NetEase Inc", "weight": "8.5%", "shares": "3.8M", "value": "$380M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "FUTU", "company": "Futu Holdings Ltd", "weight": "7.2%", "shares": "3.7M", "value": "$325M", "action": "buy", "sector": "Financial"},
            {"ticker": "JD", "company": "JD.com Inc", "weight": "6.1%", "shares": "7.6M", "value": "$275M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "CPNG", "company": "Coupang Inc", "weight": "5.4%", "shares": "10.2M", "value": "$245M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "BGNE", "company": "BeiGene Ltd", "weight": "4.8%", "shares": "1.1M", "value": "$215M", "action": "hold", "sector": "Healthcare"},
            {"ticker": "ASML", "company": "ASML Holding NV", "weight": "3.9%", "shares": "210K", "value": "$175M", "action": "buy", "sector": "Technology"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "3.2%", "shares": "340K", "value": "$145M", "action": "hold", "sector": "Technology"}
        ]
    },
    "scion": {
        "id": "scion",
        "manager_en": "Michael Burry",
        "manager_zh": "迈克尔·伯里 (大空头)",
        "fund_name_en": "Scion Asset Management",
        "fund_name_zh": "塞恩资产 (《大空头》原型传奇操盘)",
        "avatar": "🔍",
        "portfolio_value": "$180M",
        "top_holdings_count": 8,
        "style_en": "Deep Contrarian & Macro Timing",
        "style_zh": "极度敏锐逆向择时与低估值抄底",
        "holdings": [
            {"ticker": "BABA", "company": "Alibaba Group Holding", "weight": "18.5%", "shares": "340K", "value": "$33.3M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "JD", "company": "JD.com Inc", "weight": "15.2%", "shares": "760K", "value": "$27.4M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "BIDU", "company": "Baidu Inc", "weight": "12.8%", "shares": "250K", "value": "$23.0M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "FOUR", "company": "Shift4 Payments", "weight": "8.5%", "shares": "170K", "value": "$15.3M", "action": "new", "sector": "Technology"},
            {"ticker": "C", "company": "Citigroup Inc", "weight": "7.4%", "shares": "210K", "value": "$13.3M", "action": "hold", "sector": "Financial"},
            {"ticker": "REAL", "company": "The RealReal Inc", "weight": "6.2%", "shares": "2.8M", "value": "$11.2M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "OLN", "company": "Olin Corporation", "weight": "5.8%", "shares": "220K", "value": "$10.4M", "action": "hold", "sector": "Basic Materials"},
            {"ticker": "ACEL", "company": "Accel Entertainment", "weight": "5.1%", "shares": "850K", "value": "$9.2M", "action": "hold", "sector": "Consumer Cyclical"}
        ]
    },
    "duquesne": {
        "id": "duquesne",
        "manager_en": "Stanley Druckenmiller",
        "manager_zh": "斯坦利·德鲁肯米勒",
        "fund_name_en": "Duquesne Family Office",
        "fund_name_zh": "杜肯家族办公室 (索罗斯前首席操盘手)",
        "avatar": "⚔️",
        "portfolio_value": "$3.2B",
        "top_holdings_count": 10,
        "style_en": "Macro Momentum & AI Pioneers",
        "style_zh": "顶级宏观趋势与全球 AI 基础设施",
        "holdings": [
            {"ticker": "NVO", "company": "Novo Nordisk A/S", "weight": "12.5%", "shares": "3.7M", "value": "$400M", "action": "hold", "sector": "Healthcare"},
            {"ticker": "CPNG", "company": "Coupang Inc", "weight": "11.2%", "shares": "14.9M", "value": "$358M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "8.9%", "shares": "670K", "value": "$285M", "action": "reduce", "sector": "Technology"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "7.8%", "shares": "1.9M", "value": "$250M", "action": "reduce", "sector": "Technology"},
            {"ticker": "WMT", "company": "Walmart Inc", "weight": "6.5%", "shares": "2.4M", "value": "$208M", "action": "buy", "sector": "Consumer Defensive"},
            {"ticker": "GE", "company": "GE Aerospace", "weight": "5.8%", "shares": "1.0M", "value": "$185M", "action": "buy", "sector": "Industrials"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "5.2%", "shares": "860K", "value": "$166M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "VST", "company": "Vistra Corp", "weight": "4.8%", "shares": "1.2M", "value": "$154M", "action": "buy", "sector": "Utilities"},
            {"ticker": "COHR", "company": "Coherent Corp", "weight": "4.2%", "shares": "1.4M", "value": "$134M", "action": "new", "sector": "Technology"},
            {"ticker": "LLY", "company": "Eli Lilly and Co", "weight": "3.8%", "shares": "150K", "value": "$122M", "action": "hold", "sector": "Healthcare"}
        ]
    },
    "tiger_global": {
        "id": "tiger_global",
        "manager_en": "Chase Coleman",
        "manager_zh": "蔡斯·科尔曼 / 老虎环球",
        "fund_name_en": "Tiger Global Management",
        "fund_name_zh": "老虎环球 (全球顶级科技成长对冲)",
        "avatar": "🐯",
        "portfolio_value": "$12.5B",
        "top_holdings_count": 10,
        "style_en": "High-Growth Tech Unicorns",
        "style_zh": "全球超级科技巨头与 SaaS 成长先锋",
        "holdings": [
            {"ticker": "META", "company": "Meta Platforms Inc", "weight": "21.5%", "shares": "4.8M", "value": "$2.69B", "action": "hold", "sector": "Communication Services"},
            {"ticker": "MSFT", "company": "Microsoft Corporation", "weight": "15.8%", "shares": "4.6M", "value": "$1.98B", "action": "hold", "sector": "Technology"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "12.4%", "shares": "8.5M", "value": "$1.55B", "action": "hold", "sector": "Communication Services"},
            {"ticker": "AMZN", "company": "Amazon.com Inc", "weight": "9.8%", "shares": "6.3M", "value": "$1.22B", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "NVDA", "company": "NVIDIA Corporation", "weight": "7.5%", "shares": "7.2M", "value": "$938M", "action": "buy", "sector": "Technology"},
            {"ticker": "SE", "company": "Sea Limited", "weight": "6.2%", "shares": "7.8M", "value": "$775M", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "NOW", "company": "ServiceNow Inc", "weight": "5.4%", "shares": "720K", "value": "$675M", "action": "hold", "sector": "Technology"},
            {"ticker": "UBER", "company": "Uber Technologies", "weight": "4.8%", "shares": "8.1M", "value": "$600M", "action": "buy", "sector": "Technology"},
            {"ticker": "FLUT", "company": "Flutter Entertainment", "weight": "3.9%", "shares": "1.9M", "value": "$488M", "action": "new", "sector": "Consumer Cyclical"},
            {"ticker": "CRWD", "company": "CrowdStrike Holdings", "weight": "3.2%", "shares": "1.1M", "value": "$400M", "action": "hold", "sector": "Technology"}
        ]
    },
    "ark": {
        "id": "ark",
        "manager_en": "Cathie Wood",
        "manager_zh": "凯瑟琳·伍德 (木头姐)",
        "fund_name_en": "ARK Invest",
        "fund_name_zh": "方舟投资 (颠覆式创新与硬科技)",
        "avatar": "🚀",
        "portfolio_value": "$11.2B",
        "top_holdings_count": 10,
        "style_en": "Disruptive Innovation & High Beta",
        "style_zh": "颠覆式创新科技与高弹性成长",
        "holdings": [
            {"ticker": "TSLA", "company": "Tesla Inc", "weight": "11.8%", "shares": "5.9M", "value": "$1.32B", "action": "buy", "sector": "Consumer Cyclical"},
            {"ticker": "COIN", "company": "Coinbase Global", "weight": "9.2%", "shares": "4.1M", "value": "$1.03B", "action": "hold", "sector": "Financial"},
            {"ticker": "ROKU", "company": "Roku Inc", "weight": "7.8%", "shares": "11.2M", "value": "$874M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "PLTR", "company": "Palantir Technologies", "weight": "6.5%", "shares": "15.8M", "value": "$728M", "action": "buy", "sector": "Technology"},
            {"ticker": "SQ", "company": "Block Inc", "weight": "5.9%", "shares": "8.6M", "value": "$661M", "action": "hold", "sector": "Technology"},
            {"ticker": "CRSP", "company": "CRISPR Therapeutics", "weight": "5.2%", "shares": "10.5M", "value": "$582M", "action": "buy", "sector": "Healthcare"},
            {"ticker": "HOOD", "company": "Robinhood Markets", "weight": "4.8%", "shares": "18.5M", "value": "$538M", "action": "buy", "sector": "Financial"},
            {"ticker": "SHOP", "company": "Shopify Inc", "weight": "4.2%", "shares": "4.9M", "value": "$470M", "action": "hold", "sector": "Technology"},
            {"ticker": "PATH", "company": "UiPath Inc", "weight": "3.8%", "shares": "28.5M", "value": "$425M", "action": "hold", "sector": "Technology"},
            {"ticker": "RKLB", "company": "Rocket Lab USA", "weight": "3.2%", "shares": "16.8M", "value": "$358M", "action": "buy", "sector": "Industrials"}
        ]
    },
    "oaktree": {
        "id": "oaktree",
        "manager_en": "Howard Marks",
        "manager_zh": "霍华德·马克斯 / 橡树资本",
        "fund_name_en": "Oaktree Capital Management",
        "fund_name_zh": "橡树资本 (《周期》作者 / 不良资产先锋)",
        "avatar": "🌳",
        "portfolio_value": "$7.4B",
        "top_holdings_count": 8,
        "style_en": "Distressed Debt & Cyclical Value",
        "style_zh": "周期逆向投资与高安全边际",
        "holdings": [
            {"ticker": "TRMD", "company": "TORM plc", "weight": "14.5%", "shares": "35.2M", "value": "$1.07B", "action": "hold", "sector": "Energy"},
            {"ticker": "CVI", "company": "CVR Energy Inc", "weight": "11.8%", "shares": "32.1M", "value": "$873M", "action": "hold", "sector": "Energy"},
            {"ticker": "VIST", "company": "Vista Energy S.A.B.", "weight": "8.2%", "shares": "11.8M", "value": "$607M", "action": "buy", "sector": "Energy"},
            {"ticker": "VALE", "company": "Vale S.A.", "weight": "6.5%", "shares": "43.5M", "value": "$481M", "action": "hold", "sector": "Basic Materials"},
            {"ticker": "CHTR", "company": "Charter Communications", "weight": "5.8%", "shares": "1.2M", "value": "$429M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "PBR", "company": "Petrobras ADR", "weight": "4.9%", "shares": "26.5M", "value": "$363M", "action": "hold", "sector": "Energy"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "4.2%", "shares": "1.7M", "value": "$311M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "ALL", "company": "Allstate Corp", "weight": "3.6%", "shares": "1.4M", "value": "$266M", "action": "hold", "sector": "Financial"}
        ]
    },
    "baupost": {
        "id": "baupost",
        "manager_en": "Seth Klarman",
        "manager_zh": "赛斯·卡拉曼 / 鲍波斯特",
        "fund_name_en": "Baupost Group",
        "fund_name_zh": "鲍波斯特集团 (《安全边际》作者)",
        "avatar": "🛡️",
        "portfolio_value": "$5.1B",
        "top_holdings_count": 8,
        "style_en": "Margin of Safety & Distressed Value",
        "style_zh": "极致安全边际与复杂特殊机遇",
        "holdings": [
            {"ticker": "VRNT", "company": "Verint Systems Inc", "weight": "16.5%", "shares": "28.5M", "value": "$841M", "action": "hold", "sector": "Technology"},
            {"ticker": "FIS", "company": "Fidelity National Info", "weight": "14.2%", "shares": "8.9M", "value": "$724M", "action": "buy", "sector": "Technology"},
            {"ticker": "CRH", "company": "CRH plc", "weight": "12.8%", "shares": "6.8M", "value": "$653M", "action": "hold", "sector": "Basic Materials"},
            {"ticker": "WBD", "company": "Warner Bros Discovery", "weight": "9.5%", "shares": "58.2M", "value": "$485M", "action": "buy", "sector": "Communication Services"},
            {"ticker": "GOOGL", "company": "Alphabet Inc Class A", "weight": "8.2%", "shares": "2.3M", "value": "$418M", "action": "hold", "sector": "Communication Services"},
            {"ticker": "VTRS", "company": "Viatris Inc", "weight": "7.1%", "shares": "31.5M", "value": "$362M", "action": "hold", "sector": "Healthcare"},
            {"ticker": "QSR", "company": "Restaurant Brands Intl", "weight": "6.4%", "shares": "4.5M", "value": "$326M", "action": "hold", "sector": "Consumer Cyclical"},
            {"ticker": "UNH", "company": "UnitedHealth Group", "weight": "4.8%", "shares": "420K", "value": "$245M", "action": "new", "sector": "Healthcare"}
        ]
    }
}

def apply_signal_filter(fcustom, sig_key, sig_val):
    if sig_key in CUSTOM_FILTERS:
        fcustom.set_filter(filters_dict=CUSTOM_FILTERS[sig_key])
    else:
        fcustom.set_filter(signal=sig_val)


