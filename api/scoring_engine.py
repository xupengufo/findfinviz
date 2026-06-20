from datetime import datetime, timezone
from api.cache_manager import cache
from scoring_config import (
    DIMENSION_CAPS, TECH_FACTORS, FUND_FACTORS, SENT_FACTORS,
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

def calculate_confluences():
    # Detect empty cache state
    if (cache.get("opps_oversold") is None or 
        cache.get("opps_double_bottom") is None or 
        cache.get("insiders_top_owner_trade") is None):
        return {"status": "empty", "message": "Cache is empty. Please run sync first.", "data": []}

    oversold = cache.get("opps_oversold") or []
    double_bottom = cache.get("opps_double_bottom") or []
    new_high = cache.get("opps_new_high") or []
    triangle_ascending = cache.get("opps_triangle_ascending") or []
    unusual_volume = cache.get("opps_unusual_volume") or []
    high_short_interest = cache.get("opps_high_short_interest") or []
    pullback = cache.get("opps_pullback") or []
    breakout_candidate = cache.get("opps_breakout_candidate") or []
    quality_compounder = cache.get("opps_quality_compounder") or []
    upgrades = cache.get("opps_upgrades") or []
    downgrades = cache.get("opps_downgrades") or []
    earnings_before = cache.get("opps_earnings_before") or []
    earnings_after = cache.get("opps_earnings_after") or []
    most_active = cache.get("opps_most_active") or []
    top_losers = cache.get("opps_top_losers") or []
    overbought = cache.get("opps_overbought") or []
    wedge_up = cache.get("opps_wedge_up") or []
    wedge_down = cache.get("opps_wedge_down") or []
    top_gainers = cache.get("opps_top_gainers") or []
    most_volatile = cache.get("opps_most_volatile") or []
    recent_insider_buying_signal = cache.get("opps_recent_insider_buying") or []
    
    insiders = cache.get("insiders_top_owner_trade") or []
    insiders_latest = cache.get("insiders_latest") or []
    insiders_top_week = cache.get("insiders_top_week") or []
    
    reddit = cache.get("reddit_sentiment") or []
    sectors = cache.get("sectors_performance") or []

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
                    "low_liquidity": False
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
        if not entry["ADTV"] and adtv: entry["ADTV"] = adtv
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

        tech_dim = max(min(tech_dim, DIMENSION_CAPS["tech"]), 0)

        # 2. Fundamentals & Corporate Insiders (Max 30)
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

        # Quality compounder + downgrade conflict
        if e["Factors"]["quality_compounder"] and e["Factors"]["analyst_downgrade"]:
            conflicts.append("conflict_quality_downgrade")

        fund_dim = max(min(fund_dim, DIMENSION_CAPS["fund"]), 0)

        # 3. Market Sentiment & Flow (Max 15)
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

        sent_dim = max(min(sent_dim, DIMENSION_CAPS["sent"]), 0)

        # 4. Valuation (Max 5)
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
        val_dim = max(min(val_dim, DIMENSION_CAPS["val"]), 0)

        # 5. Relative Strength vs SPY (Max 20)
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
        rs_dim = max(min(rs_dim, DIMENSION_CAPS["rs"]), 0)

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
        e["Reasons"] = reasons
        e["Conflicts"] = conflicts

        dims_with_score = sum([1 for d in [tech_dim, fund_dim, sent_dim, val_dim, rs_dim] if d > 0])
        if e["Score"] >= MIN_SCORE and dims_with_score >= MIN_DIMENSIONS:
            res_list.append(e)

    res_list = sorted(res_list, key=lambda x: x["Score"], reverse=True)
    return {"data": res_list, "source": "live", "updated_at": datetime.now(timezone.utc).isoformat()}
