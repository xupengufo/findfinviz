from datetime import datetime, timezone
from api.cache_manager import cache
from scoring_config import (
    DIMENSION_CAPS, STRATEGY_PROFILES, TECH_FACTORS, FUND_FACTORS, SENT_FACTORS,
    VALUATION, RS_SCORING, MIN_SCORE, MIN_DIMENSIONS, LIQUIDITY_FLOOR
)

def normalize_change_pct(val):
    """Normalize Change value to a percentage float.
    Handles both '5.00%' string and 0.05 decimal formats."""
    if val is None or val == '':
        return 0.0
    try:
        s = str(val).strip()
        if '%' in s:
            return float(s.replace('%', ''))
        else:
            return float(s) * 100
    except:
        return 0.0

def get_field(item, *possible_keys):
    """Robustly fetch a field from a FinViz screener record.
    FinViz HTML table headers inconsistently mix full names
    ('Forward P/E') and abbreviations ('P/FCF', 'ROE'), so try
    multiple candidates and return the first non-empty match."""
    if not item:
        return ""
    for k in possible_keys:
        v = item.get(k)
        if v is not None and v != "" and str(v).lower() != "nan":
            return v
    return ""

def parse_earnings_info(earnings_str):
    """Parses FinViz earnings date string (e.g. 'Feb 26/a', 'Feb 26/b', 'Mar 04')
    and determines if earnings are imminent (within 7 days)."""
    if not earnings_str or str(earnings_str).strip() in ["", "-", "nan", "None"]:
        return None

    raw = str(earnings_str).strip()
    s = raw
    session = ""
    if "/a" in s.lower():
        session = "AMC" # After market close
        s = s.lower().replace("/a", "").strip()
    elif "/b" in s.lower():
        session = "BMO" # Before market open
        s = s.lower().replace("/b", "").strip()

    now = datetime.now(timezone.utc)
    current_year = now.year

    diff_days = None
    is_imminent = False
    display_str = raw

    for fmt in ["%b %d %Y", "%m/%d/%Y", "%Y-%m-%d"]:
        try:
            target_str = f"{s} {current_year}" if not any(c in s for c in ["/", "-"]) else s
            dt = datetime.strptime(target_str, fmt).replace(tzinfo=timezone.utc)
            diff_days = (dt.date() - now.date()).days
            if diff_days < -30:
                dt = datetime.strptime(f"{s} {current_year + 1}", fmt).replace(tzinfo=timezone.utc)
                diff_days = (dt.date() - now.date()).days
            is_imminent = (0 <= diff_days <= 7)
            display_str = dt.strftime("%b %d") + (f" ({session})" if session else "")
            break
        except Exception:
            continue

    return {
        "raw": raw,
        "display": display_str,
        "days_until": diff_days,
        "is_imminent": is_imminent,
        "session": session
    }

def compute_trade_setup(price_val, atr_val, target_price_val, high_52w_val=None):
    """Calculates dynamic stop loss, profit target, and Risk/Reward ratio based on ATR."""
    try:
        price = float(str(price_val).replace("$", "").replace(",", "").strip())
        if price <= 0:
            return None
    except (ValueError, TypeError):
        return None

    atr = None
    try:
        if atr_val:
            atr = float(str(atr_val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        pass

    if not atr or atr <= 0:
        atr = round(price * 0.035, 2)  # 3.5% volatility proxy

    # Stop Loss: 1.5 * ATR below current price
    stop_loss = round(max(0.01, price - 1.5 * atr), 2)
    risk_amount = round(price - stop_loss, 2)
    risk_pct = round(- (risk_amount / price) * 100, 1)

    # Target Price: Prefer Analyst Target Price if > Price * 1.02, else Price + 3.0 * ATR
    target = None
    try:
        if target_price_val:
            tp = float(str(target_price_val).replace("$", "").replace(",", "").strip())
            if tp > price * 1.02:
                target = tp
    except (ValueError, TypeError):
        pass

    if not target:
        target = round(price + 3.0 * atr, 2)

    target = round(target, 2)
    reward_amount = round(target - price, 2)
    reward_pct = round((reward_amount / price) * 100, 1)

    rr_ratio = round(reward_amount / max(0.01, risk_amount), 1)
    is_high_rr = (rr_ratio >= 3.0)

    return {
        "atr": round(atr, 2),
        "entry_price": round(price, 2),
        "stop_loss": stop_loss,
        "stop_loss_pct": risk_pct,
        "target_price": target,
        "target_price_pct": reward_pct,
        "rr_ratio": rr_ratio,
        "is_high_rr": is_high_rr
    }

def calculate_confluences(strategy: str = "all"):
    profile = STRATEGY_PROFILES.get(strategy, STRATEGY_PROFILES["all"])
    dim_caps = profile["dim_caps"]
    min_score = profile.get("min_score", MIN_SCORE)
    min_dimensions = profile.get("min_dimensions", MIN_DIMENSIONS)
    required_factors = profile.get("required_factors", [])

    keys_to_fetch = [
        "opps_oversold", "opps_double_bottom", "opps_new_high", "opps_triangle_ascending",
        "opps_unusual_volume", "opps_high_short_interest", "opps_pullback", "opps_breakout_candidate",
        "opps_quality_compounder", "opps_upgrades", "opps_downgrades", "opps_earnings_before",
        "opps_earnings_after", "opps_most_active", "opps_top_losers", "opps_overbought",
        "opps_wedge_up", "opps_wedge_down", "opps_top_gainers", "opps_most_volatile",
        "opps_recent_insider_buying", "insiders_top_owner_trade", "insiders_latest",
        "insiders_top_week", "reddit_sentiment", "sectors_performance"
    ]
    
    cached_map = cache.mget(keys_to_fetch)

    # Detect empty cache state
    if (cached_map.get("opps_oversold") is None or 
        cached_map.get("opps_double_bottom") is None or 
        cached_map.get("insiders_top_owner_trade") is None):
        return {"status": "empty", "message": "Cache is empty. Please run sync first.", "data": [], "strategy": profile["id"], "profile": profile}

    oversold = cached_map.get("opps_oversold") or []
    double_bottom = cached_map.get("opps_double_bottom") or []
    new_high = cached_map.get("opps_new_high") or []
    triangle_ascending = cached_map.get("opps_triangle_ascending") or []
    unusual_volume = cached_map.get("opps_unusual_volume") or []
    high_short_interest = cached_map.get("opps_high_short_interest") or []
    pullback = cached_map.get("opps_pullback") or []
    breakout_candidate = cached_map.get("opps_breakout_candidate") or []
    quality_compounder = cached_map.get("opps_quality_compounder") or []
    upgrades = cached_map.get("opps_upgrades") or []
    downgrades = cached_map.get("opps_downgrades") or []
    earnings_before = cached_map.get("opps_earnings_before") or []
    earnings_after = cached_map.get("opps_earnings_after") or []
    most_active = cached_map.get("opps_most_active") or []
    top_losers = cached_map.get("opps_top_losers") or []
    overbought = cached_map.get("opps_overbought") or []
    wedge_up = cached_map.get("opps_wedge_up") or []
    wedge_down = cached_map.get("opps_wedge_down") or []
    top_gainers = cached_map.get("opps_top_gainers") or []
    most_volatile = cached_map.get("opps_most_volatile") or []
    recent_insider_buying_signal = cached_map.get("opps_recent_insider_buying") or []
    
    insiders = cached_map.get("insiders_top_owner_trade") or []
    insiders_latest = cached_map.get("insiders_latest") or []
    insiders_top_week = cached_map.get("insiders_top_week") or []
    
    reddit = cached_map.get("reddit_sentiment") or []
    sectors = cached_map.get("sectors_performance") or []

    tickers_map = {}

    def get_or_create_ticker(ticker, company, sector, industry, price, change, mcap, pe, float_short, rel_vol, roe=None, debt_equity=None, item=None):
        t = ticker.upper()
        
        # If item is passed, robustly extract using get_field with all variants
        if item:
            company = get_field(item, "Company", "Name") or company
            sector = get_field(item, "Sector") or sector
            industry = get_field(item, "Industry") or industry
            price = get_field(item, "Price") or price
            change = get_field(item, "Change") or change
            mcap = get_field(item, "Market Cap", "Market Cap.", "Market Capitalization", "Mkt Cap") or mcap
            pe = get_field(item, "P/E", "PE", "P/E Ratio") or pe
            float_short = get_field(item, "Short Float", "Float Short", "Short Float %", "Float Short %") or float_short
            rel_vol = get_field(item, "Rel Volume", "Relative Volume", "Rel Vol", "Relative Vol") or rel_vol
            roe = get_field(item, "ROE", "Return on Equity", "Return on Equity %") or roe
            debt_equity = get_field(item, "Debt/Eq", "Total Debt/Equity", "Total Debt/Eq", "Debt/Equity") or debt_equity
            
        # Extract valuation fields if item is provided (try common name variants)
        fwd_pe = get_field(item, "Forward P/E", "Fwd P/E")
        peg = get_field(item, "PEG")
        p_fcf = get_field(item, "P/FCF", "P/Free Cash Flow")
        
        # Multi-day performance for TechScore momentum + Relative Strength (P0-1/P0-2)
        perf_week = get_field(item, "Perf Week", "Performance (Week)")
        perf_month = get_field(item, "Perf Month", "Performance (Month)")
        perf_quarter = get_field(item, "Perf Quart", "Performance (Quarter)")
        
        # Average volume for ADTV liquidity filter (P0-3)
        avg_volume = get_field(item, "Avg Volume", "Average Volume")

        # ATR, Target Price, 52W High, Earnings Date for Trade Setup & Earnings Warning
        atr = get_field(item, "Average True Range", "ATR")
        target_price = get_field(item, "Target Price")
        high_52w = get_field(item, "52-Week High", "52W High")
        earnings_date = get_field(item, "Earnings Date")

        # Institutional Ownership & Transactions
        inst_own = get_field(item, "Inst Own", "Institutional Ownership", "Institutional Ownership %")
        inst_trans = get_field(item, "Inst Trans", "Institutional Transactions", "Institutional Transactions %")

        # Compute ADTV (Average Daily Trading Value) = avg_volume × price
        adtv = ""
        try:
            av = float(avg_volume) if avg_volume else 0
            pr = float(price) if price else 0
            if av > 0 and pr > 0:
                adtv = av * pr
        except (ValueError, TypeError):
            pass

        if t not in tickers_map:
            tickers_map[t] = {
                "Ticker": t,
                "Company": company or "",
                "Sector": sector or "",
                "Industry": industry or "",
                "Price": price or "",
                "Change": change or "",
                "Market Cap": mcap or "",
                "P/E": pe or "",
                "Forward P/E": fwd_pe or "",
                "PEG": peg or "",
                "P/FCF": p_fcf or "",
                "Short Float": float_short or "",
                "Rel Volume": rel_vol or "",
                "ROE": roe or "",
                "Debt/Eq": debt_equity or "",
                "Perf Week": perf_week or "",
                "Perf Month": perf_month or "",
                "Perf Quarter": perf_quarter or "",
                "Avg Volume": avg_volume or "",
                "ATR": atr or "",
                "Target Price": target_price or "",
                "52W High": high_52w or "",
                "Earnings Date": earnings_date or "",
                "Inst Own": inst_own or "",
                "Inst Trans": inst_trans or "",
                "ADTV": adtv,
                "Score": 0,
                "TechScore": 0,
                "Reasons": [],
                "Conflicts": [],
                "Factors": {
                    "reversal": False,
                    "breakout": False,
                    "volume_spike": False,
                    "high_volatility": False,
                    "short_squeeze": False,
                    "insider_buying": False,
                    "reddit_popular": False,
                    "strong_sector": False,
                    "pullback": False,
                    "breakout_candidate": False,
                    "quality_compounder": False,
                    "analyst_upgrade": False,
                    "earnings_catalyst": False,
                    "momentum_leader": False,
                    "analyst_downgrade": False,
                    "overbought": False,
                    "bearish_momentum": False,
                    "low_liquidity": False,
                    "inst_accumulation": False,
                    "inst_high_ownership": False,
                    "inst_distribution": False
                }
            }
        entry = tickers_map[t]
        if not entry["Company"] and company: entry["Company"] = company
        if not entry["Sector"] and sector: entry["Sector"] = sector
        if not entry["Industry"] and industry: entry["Industry"] = industry
        if not entry["Price"] and price: entry["Price"] = price
        if not entry["Change"] and change: entry["Change"] = change
        if not entry["Market Cap"] and mcap: entry["Market Cap"] = mcap
        if not entry["P/E"] and pe: entry["P/E"] = pe
        if not entry["Forward P/E"] and fwd_pe: entry["Forward P/E"] = fwd_pe
        if not entry["PEG"] and peg: entry["PEG"] = peg
        if not entry["P/FCF"] and p_fcf: entry["P/FCF"] = p_fcf
        if not entry["Short Float"] and float_short: entry["Short Float"] = float_short
        if not entry["Rel Volume"] and rel_vol: entry["Rel Volume"] = rel_vol
        if not entry["ROE"] and roe: entry["ROE"] = roe
        if not entry["Debt/Eq"] and debt_equity: entry["Debt/Eq"] = debt_equity
        if not entry["Perf Week"] and perf_week: entry["Perf Week"] = perf_week
        if not entry["Perf Month"] and perf_month: entry["Perf Month"] = perf_month
        if not entry["Perf Quarter"] and perf_quarter: entry["Perf Quarter"] = perf_quarter
        if not entry["Avg Volume"] and avg_volume: entry["Avg Volume"] = avg_volume
        if not entry.get("ATR") and atr: entry["ATR"] = atr
        if not entry.get("Target Price") and target_price: entry["Target Price"] = target_price
        if not entry.get("52W High") and high_52w: entry["52W High"] = high_52w
        if not entry.get("Earnings Date") and earnings_date: entry["Earnings Date"] = earnings_date
        if not entry["ADTV"] and adtv: entry["ADTV"] = adtv
        return entry
        return entry

    for item in oversold:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["reversal"] = True

    for item in double_bottom:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["reversal"] = True

    for item in new_high:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in triangle_ascending:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in unusual_volume:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["volume_spike"] = True

    for item in high_short_interest:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["short_squeeze"] = True

    for item in pullback:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["pullback"] = True

    for item in breakout_candidate:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout_candidate"] = True

    for item in quality_compounder:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["quality_compounder"] = True

    for item in upgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["analyst_upgrade"] = True

    for item in earnings_before + earnings_after:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["earnings_catalyst"] = True

    for item in most_active + top_gainers:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["momentum_leader"] = True

    for item in recent_insider_buying_signal:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["insider_buying"] = True

    for item in insiders + insiders_latest + insiders_top_week:
        ticker = item.get("Ticker")
        txn = item.get("Transaction")
        if ticker and txn and "buy" in txn.lower():
            e = get_or_create_ticker(ticker, "", "", "", "", "", "", "", "", "", None, None)
            e["Factors"]["insider_buying"] = True

    for item in reddit[:50]:
        ticker = item.get("ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("name"), "", "", "", "", "", "", "", "", None, None)
            e["Factors"]["reddit_popular"] = True

    for item in top_losers:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["bearish_momentum"] = True

    for item in wedge_up:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    # Wedge Down is a bullish continuation pattern, classified as breakout
    for item in wedge_down:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["breakout"] = True

    for item in overbought:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["overbought"] = True

    # Most Volatile is a volatility signal, not volume; track separately
    for item in most_volatile:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["high_volatility"] = True

    for item in downgrades:
        ticker = item.get("Ticker")
        if ticker:
            e = get_or_create_ticker(ticker, item.get("Company"), item.get("Sector"), item.get("Industry"), item.get("Price"), item.get("Change"), item.get("Market Cap"), item.get("P/E"), item.get("Short Float"), item.get("Rel Volume"), item.get("ROE"), item.get("Debt/Eq"), item)
            e["Factors"]["analyst_downgrade"] = True

    top_3_sectors = []
    try:
        def parse_pct(s):
            try:
                return float(str(s).replace("%", "").strip())
            except:
                return -999.0
        sorted_sectors = sorted(sectors, key=lambda x: parse_pct(x.get("Change", 0)), reverse=True)
        top_3_sectors = [x.get("Name") for x in sorted_sectors[:3] if x.get("Name")]
    except Exception as ex:
        print("Error sorting sectors:", ex)

    for ticker, e in tickers_map.items():
        try:
            adtv = float(e.get("ADTV") or 0)
            if adtv <= 0 or adtv < LIQUIDITY_FLOOR:
                e["Factors"]["low_liquidity"] = True
        except (ValueError, TypeError):
            e["Factors"]["low_liquidity"] = True

    spy_perf = {"5d": 0.0, "20d": 0.0, "63d": 0.0}
    try:
        turb_cache = cache.get("market_turbulence")
        if turb_cache and turb_cache.get("chart_series"):
            cs = turb_cache["chart_series"]
            spy_prices = [pt.get("spx", 0) for pt in cs if pt.get("spx", 0) > 0]
            if len(spy_prices) >= 65:
                spy_perf["5d"] = (spy_prices[-1] / spy_prices[-6] - 1) * 100
                spy_perf["20d"] = (spy_prices[-1] / spy_prices[-21] - 1) * 100
                spy_perf["63d"] = (spy_prices[-1] / spy_prices[-64] - 1) * 100
    except Exception as ex:
        print("Error computing SPY benchmark:", ex)

    res_list = []
    for ticker, e in tickers_map.items():
        reasons = []
        conflicts = []

        # 1. Technical Structure (Max 30)
        tech_dim = 0
        core_patterns = []
        if e["Factors"]["reversal"]:
            core_patterns.append((TECH_FACTORS["reversal"], "reason_reversal"))
        if e["Factors"]["pullback"]:
            core_patterns.append((TECH_FACTORS["pullback"], "reason_pullback"))
        if e["Factors"]["breakout"]:
            core_patterns.append((TECH_FACTORS["breakout"], "reason_breakout"))
        if e["Factors"]["breakout_candidate"]:
            core_patterns.append((TECH_FACTORS["breakout_candidate"], "reason_breakout_candidate"))

        if core_patterns:
            core_patterns.sort(key=lambda x: x[0], reverse=True)
            tech_dim += core_patterns[0][0]
            reasons.append(core_patterns[0][1])

            # Confirmation bonus for multiple aligned patterns
            if len(core_patterns) > 1:
                confirm_bonus = min((len(core_patterns) - 1) * TECH_FACTORS["confirm_bonus_per"],
                                     TECH_FACTORS["confirm_bonus_cap"])
                tech_dim += confirm_bonus
                for val, reason_key in core_patterns[1:]:
                    reasons.append(reason_key)

        if e["Factors"]["volume_spike"]:
            tech_dim += TECH_FACTORS["volume_spike"]
            reasons.append("reason_volume_spike")

        if e["Factors"]["high_volatility"]:
            tech_dim += TECH_FACTORS["high_volatility"]
            reasons.append("reason_high_volatility")

        if e["Sector"] in top_3_sectors:
            e["Factors"]["strong_sector"] = True
            tech_dim += TECH_FACTORS["strong_sector"]
            reasons.append("reason_strong_sector")

        # Signal conflict detection
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            tech_dim += TECH_FACTORS["conflict_overbought_reversal"]
            conflicts.append("conflict_overbought_reversal")

        if e["Factors"]["overbought"] and e["Factors"]["breakout"]:
            conflicts.append("conflict_overbought_breakout")

        if e["Factors"]["reversal"] and e["Factors"]["bearish_momentum"]:
            tech_dim += TECH_FACTORS["conflict_reversal_bearish"]
            conflicts.append("conflict_reversal_bearish")

        tech_dim = max(min(tech_dim * (dim_caps["tech"] / 30.0), dim_caps["tech"]), 0)

        # 2. Fundamentals & Corporate Insiders (Max 30 default)
        fund_dim = 0
        if e["Factors"]["insider_buying"]:
            fund_dim += FUND_FACTORS["insider_buying"]
            reasons.append("reason_insider_buying")
        if e["Factors"]["quality_compounder"]:
            fund_dim += FUND_FACTORS["quality_compounder"]
            reasons.append("reason_quality_compounder")
        if e["Factors"]["analyst_upgrade"]:
            fund_dim += FUND_FACTORS["analyst_upgrade"]
            reasons.append("reason_analyst_upgrade")
        if e["Factors"]["earnings_catalyst"]:
            fund_dim += FUND_FACTORS["earnings_catalyst"]
            reasons.append("reason_earnings_catalyst")
        if e["Factors"]["analyst_downgrade"]:
            fund_dim += FUND_FACTORS["analyst_downgrade"]
            reasons.append("reason_analyst_downgrade")

        # Institutional Flow & Ownership Factors
        inst_trans_val = None
        try:
            it_raw = str(e.get("Inst Trans", "")).replace("%", "").strip()
            if it_raw and it_raw != "-":
                raw_f = float(it_raw)
                inst_trans_val = raw_f if "%" in str(e.get("Inst Trans")) or abs(raw_f) > 1.0 else raw_f * 100
        except (ValueError, TypeError):
            pass

        inst_own_val = None
        try:
            io_raw = str(e.get("Inst Own", "")).replace("%", "").strip()
            if io_raw and io_raw != "-":
                raw_o = float(io_raw)
                inst_own_val = raw_o if "%" in str(e.get("Inst Own")) or abs(raw_o) > 1.0 else raw_o * 100
        except (ValueError, TypeError):
            pass

        if inst_trans_val is not None:
            if inst_trans_val >= 5.0:  # >= +5% institutional net accumulation
                e["Factors"]["inst_accumulation"] = True
                fund_dim += 6
                reasons.append("reason_inst_accumulation")
            elif inst_trans_val <= -5.0:  # <= -5% institutional net distribution
                e["Factors"]["inst_distribution"] = True
                conflicts.append("conflict_inst_distribution")

        if inst_own_val is not None and inst_own_val >= 70.0:  # >= 70% institutional ownership
            e["Factors"]["inst_high_ownership"] = True
            fund_dim += 3
            reasons.append("reason_inst_high_ownership")

        # Quality compounder + downgrade conflict
        if e["Factors"]["quality_compounder"] and e["Factors"]["analyst_downgrade"]:
            conflicts.append("conflict_quality_downgrade")

        fund_dim = max(min(fund_dim * (dim_caps["fund"] / 30.0), dim_caps["fund"]), 0)

        # 3. Market Sentiment & Flow (Max 15 default)
        sent_dim = 0
        if e["Factors"]["momentum_leader"]:
            sent_dim += SENT_FACTORS["momentum_leader"]
            reasons.append("reason_momentum_leader")
        if e["Factors"]["reddit_popular"]:
            sent_dim += SENT_FACTORS["reddit_popular"]
            reasons.append("reason_reddit_popular")
        if e["Factors"]["short_squeeze"]:
            if e["Factors"]["reddit_popular"] or e["Factors"]["reversal"] or e["Factors"]["breakout"] or e["Factors"]["volume_spike"]:
                sent_dim += SENT_FACTORS["short_squeeze_combined"]
                reasons.append("reason_squeeze_play")
            else:
                sent_dim += SENT_FACTORS["short_squeeze_alone"]
                reasons.append("reason_high_short_float")
        if e["Factors"]["bearish_momentum"]:
            sent_dim += SENT_FACTORS["bearish_momentum"]
            reasons.append("reason_bearish_momentum")

        sent_dim = max(min(sent_dim * (dim_caps["sent"] / 15.0), dim_caps["sent"]), 0)

        # 4. Valuation (Max 5 default)
        val_dim = 0
        try:
            fwd_pe_str = str(e.get("Forward P/E") or "").strip()
            peg_str = str(e.get("PEG") or "").strip()

            fwd_pe = float(fwd_pe_str) if fwd_pe_str and fwd_pe_str != "-" else 0.0
            peg = float(peg_str) if peg_str and peg_str != "-" else 0.0

            lo, hi, sc = VALUATION["fwd_pe_undervalued"]
            if lo < fwd_pe <= hi:
                val_dim += sc; reasons.append("reason_valuation_undervalued")
            else:
                lo, hi, sc = VALUATION["fwd_pe_fair"]
                if lo < fwd_pe <= hi:
                    val_dim += sc; reasons.append("reason_valuation_fair")
                else:
                    lo, hi, sc = VALUATION["fwd_pe_high_ok"]
                    if lo < fwd_pe <= hi:
                        val_dim += sc; reasons.append("reason_valuation_high_but_acceptable")

            lo, hi, sc = VALUATION["peg_undervalued"]
            if lo < peg <= hi:
                val_dim += sc; reasons.append("reason_peg_undervalued")
            else:
                lo, hi, sc = VALUATION["peg_fair"]
                if lo < peg <= hi:
                    val_dim += sc; reasons.append("reason_peg_fair")
                else:
                    lo, hi, sc = VALUATION["peg_expensive"]
                    if lo < peg <= hi:
                        val_dim += sc; reasons.append("reason_peg_expensive")
        except Exception:
            pass
        val_dim = max(min(val_dim * (dim_caps["val"] / 5.0), dim_caps["val"]), 0)

        # 5. Relative Strength vs SPY (Max 20 default)
        rs_dim = 0
        try:
            stock_5d = normalize_change_pct(e.get("Perf Week"))
            stock_20d = normalize_change_pct(e.get("Perf Month"))
            stock_63d = normalize_change_pct(e.get("Perf Quarter"))

            excess_5d = stock_5d - spy_perf["5d"]
            excess_20d = stock_20d - spy_perf["20d"]
            excess_63d = stock_63d - spy_perf["63d"]

            positive_count = sum(1 for x in [excess_5d, excess_20d, excess_63d] if x > 0)
            rising = excess_5d > excess_20d > excess_63d

            if positive_count == 3 and rising:
                rs_dim = RS_SCORING["all_three_positive_and_rising"]
                reasons.append("reason_rs_leader")
            elif positive_count >= 2:
                rs_dim = RS_SCORING["two_of_three_positive"]
                reasons.append("reason_rs_strong")
            elif positive_count >= 1:
                rs_dim = RS_SCORING["one_of_three_positive"]
                reasons.append("reason_rs_neutral")
        except Exception:
            pass
        rs_dim = max(min(rs_dim * (dim_caps["rs"] / 20.0), dim_caps["rs"]), 0)

        tech_dim = round(tech_dim)
        fund_dim = round(fund_dim)
        sent_dim = round(sent_dim)
        val_dim = round(val_dim)
        rs_dim = round(rs_dim)

        score = tech_dim + fund_dim + sent_dim + val_dim + rs_dim

        tech_score = 0
        pattern_score = 0
        pattern_count = 0
        if e["Factors"]["breakout"]:
            pattern_score = max(pattern_score, 35)
            pattern_count += 1
        if e["Factors"]["breakout_candidate"]:
            pattern_score = max(pattern_score, 30)
            pattern_count += 1
        if e["Factors"]["pullback"]:
            pattern_score = max(pattern_score, 28)
            pattern_count += 1
        if e["Factors"]["reversal"]:
            pattern_score = max(pattern_score, 25)
            pattern_count += 1
        if pattern_count >= 2:
            pattern_score = min(pattern_score + 5, 40)
        tech_score += min(pattern_score, 40)
            
        try:
            rvol = float(e["Rel Volume"]) if e["Rel Volume"] else 0
            if rvol >= 2.0:
                tech_score += 25
            elif rvol >= 1.5:
                tech_score += 15
            elif rvol >= 1.0:
                tech_score += 10
        except:
            pass
            
        try:
            perf_5d = normalize_change_pct(e.get("Perf Week"))
            perf_20d = normalize_change_pct(e.get("Perf Month"))

            momentum_score = 0
            if e["Factors"]["reversal"]:
                if -10.0 <= perf_5d <= -1.0:
                    momentum_score += 12
                elif -20.0 <= perf_5d < -10.0:
                    momentum_score += 8
                elif perf_5d > 0:
                    momentum_score += 4
            else:
                if perf_5d > 5.0:
                    momentum_score += 12
                elif perf_5d > 2.0:
                    momentum_score += 8
                elif perf_5d > 0:
                    momentum_score += 4

            if perf_20d > 10.0:
                momentum_score += 8
            elif perf_20d > 0:
                momentum_score += 4

            tech_score += min(momentum_score, 20)
        except:
            pass
            
        trend_bonus = 0
        if e["Sector"] in top_3_sectors:
            trend_bonus += 10
        if e["Factors"]["overbought"] and (e["Factors"]["reversal"] or e["Factors"]["pullback"]):
            trend_bonus -= 5
        tech_score += max(min(trend_bonus, 15), 0)

        e["TechScore"] = min(tech_score, 100)
        e["Score"] = score
        e["ScoreBreakdown"] = {
            "tech": tech_dim,
            "fund": fund_dim,
            "sent": sent_dim,
            "val": val_dim,
            "rs": rs_dim
        }
        # Compute Trade Setup (ATR, Stop Loss, Target Price, R:R)
        trade_setup = compute_trade_setup(e.get("Price"), e.get("ATR"), e.get("Target Price"), e.get("52W High"))
        if trade_setup:
            e["TradeSetup"] = trade_setup
            if trade_setup.get("is_high_rr"):
                reasons.append("reason_high_rr")

        # Parse Earnings Info (Earnings Proximity Warning)
        earnings_info = parse_earnings_info(e.get("Earnings Date"))
        if earnings_info:
            e["EarningsInfo"] = earnings_info
            if earnings_info.get("is_imminent"):
                conflicts.append("warning_earnings_imminent")

        e["Reasons"] = reasons
        e["Conflicts"] = conflicts

        # Strategy specific factor gating
        if required_factors:
            matches_strategy = any(e["Factors"].get(f) for f in required_factors)
            if not matches_strategy:
                if strategy == "momentum" and rs_dim >= dim_caps["rs"] * 0.6:
                    matches_strategy = True
            if not matches_strategy:
                continue

        dims_with_score = sum([1 for d in [tech_dim, fund_dim, sent_dim, val_dim, rs_dim] if d > 0])
        if e["Score"] >= min_score and dims_with_score >= min_dimensions:
            res_list.append(e)

    res_list = sorted(res_list, key=lambda x: x["Score"], reverse=True)
    return {
        "data": res_list,
        "source": "live",
        "strategy": profile["id"],
        "profile": profile,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
