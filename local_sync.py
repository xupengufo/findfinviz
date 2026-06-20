import os
import sys
import json
import time
import random
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

from quant_models import retry_with_backoff, calculate_market_turbulence, calculate_sigmoid_position, MACRO_TICKERS, SECTOR_TICKERS

# Load environment variables from .env.local
env_file = ".env.local"
if os.path.exists(env_file):
    print(f"Loading environment from {env_file}...")
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                val = val.strip("'\"")
                os.environ[key] = val
else:
    print(f"Warning: {env_file} not found. Ensure KV_REST_API_URL and KV_REST_API_TOKEN are set in your environment.")

import redis

redis_url = os.environ.get("REDIS_URL") or os.environ.get("KV_URL") or os.environ.get("KV_REST_API_URL")
is_redis_rest = False
client = None
is_redis = bool(redis_url)
project_root = os.path.dirname(os.path.abspath(__file__))

def get_db_path():
    if os.environ.get("VERCEL") or not os.access(project_root, os.W_OK):
        return "/tmp/cache.db"
    api_db = os.path.join(project_root, "api", "cache.db")
    if os.path.exists(os.path.dirname(api_db)):
        return api_db
    return os.path.join(project_root, "cache.db")

if is_redis:
    if redis_url.startswith("http"):
        is_redis_rest = True
        kv_url = redis_url
        kv_token = os.environ.get("KV_REST_API_TOKEN")
        headers = {"Authorization": f"Bearer {kv_token}"}
    else:
        try:
            client = redis.from_url(redis_url, decode_responses=True)
            print("Connected to Redis server.")
        except Exception as e:
            print("Failed to connect to Redis server, falling back to SQLite cache.db:", e)
            is_redis = False
else:
    print("Vercel Redis credentials missing. Falling back to SQLite cache.db for local caching.")
    db_path = get_db_path()
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT, expires_at INTEGER)"
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print("Failed to initialize SQLite cache:", e)

# Import local finvizfinance package
if project_root not in sys.path:
    sys.path.insert(0, project_root)
finviz_dir = os.path.join(project_root, "finvizfinance")
if finviz_dir not in sys.path:
    sys.path.insert(0, finviz_dir)
from finvizfinance.insider import Insider
from finvizfinance.screener.custom import Custom
from finvizfinance.group.overview import Overview as GroupOverview

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
    # below 20-day SMA with RSI cooling (<50). A real pullback, not just "not overbought".
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
    # (good company ≠ good timing; require price above 200-day SMA)
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
# Kept explicit + commented so future changes don't require decoding magic numbers.
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
    42,  # Performance (Week)  ≈ 5-day return  — used for TechScore momentum + RS
    43,  # Performance (Month) ≈ 20-day return — used for TechScore momentum + RS
    44,  # Performance (Quarter) ≈ 60-day return — used for RS
    63,  # Average Volume       — used for ADTV (liquidity) filtering
    64,  # Relative Volume
    65,  # Price
    66,  # Change
    67,  # Volume
]

def apply_signal_filter(fcustom, sig_key, sig_val):
    if sig_key in CUSTOM_FILTERS:
        fcustom.set_filter(filters_dict=CUSTOM_FILTERS[sig_key])
    else:
        fcustom.set_filter(signal=sig_val)

def push_to_kv(key, data, expires_in=172800):  # Default 48 hours cache on KV for safety
    val_str = json.dumps(data)
    if is_redis:
        if is_redis_rest:
            url = f"{kv_url}/set/{key}?ex={expires_in}"
            try:
                res = requests.post(url, headers=headers, data=val_str, timeout=10)
                if res.status_code == 200 and res.json().get("result") == "OK":
                    print(f"Successfully pushed key '{key}' to Vercel KV (REST).")
                    return True
                else:
                    print(f"Failed to push key '{key}' (REST):", res.status_code, res.text)
                    return False
            except Exception as e:
                print(f"Error pushing key '{key}' (REST):", e)
                return False
        else:
            try:
                client.setex(key, expires_in, val_str)
                print(f"Successfully pushed key '{key}' to Vercel Redis.")
                return True
            except Exception as e:
                print(f"Error pushing key '{key}' to Redis:", e)
                return False
    else:
        try:
            import sqlite3
            from datetime import datetime, timezone
            expires_at = int(datetime.now(timezone.utc).timestamp()) + expires_in
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")
            cursor.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) VALUES (?, ?, ?)",
                (key, val_str, expires_at)
            )
            conn.commit()
            conn.close()
            print(f"Successfully pushed key '{key}' to local SQLite cache.")
            return True
        except Exception as e:
            print(f"Error pushing key '{key}' to SQLite:", e)
            return False

def sync_opportunities():
    for key, signal_name in SUPPORTED_SIGNALS.items():
        print(f"Scraping opportunities for signal: {signal_name}...")

        def do_scrape(sig_key=key, sig_val=signal_name):
            fcustom = Custom()
            apply_signal_filter(fcustom, sig_key, sig_val)
            return fcustom.screener_view(
                limit=100, 
                order="Market Cap.", 
                ascend=False, 
                verbose=0, 
                columns=SCREENER_COLUMNS
            )

        try:
            df = retry_with_backoff(do_scrape)
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            push_to_kv(f"opps_{key}", data)
            time.sleep(1.5)
        except Exception as e:
            print(f"Failed to scrape signal '{signal_name}' after retries:", e)

def sync_insiders():
    options = ["latest", "top week", "top owner trade"]
    for opt in options:
        print(f"Scraping insider trades for option: {opt}...")

        def do_scrape(option=opt):
            finsider = Insider(option=option)
            return finsider.get_insider()

        try:
            df = retry_with_backoff(do_scrape)
            data = []
            if df is not None:
                df = df.fillna("")
                data = df.to_dict(orient="records")
            key_name = f"insiders_{opt.lower().replace(' ', '_')}"
            push_to_kv(key_name, data)
            time.sleep(1.5)
        except Exception as e:
            print(f"Failed to scrape insider option '{opt}' after retries:", e)

def sync_sectors():
    print("Scraping sector performance matrix...")
    def do_scrape_sec():
        fgoverview = GroupOverview()
        return fgoverview.screener_view(group="Sector")

    try:
        df = retry_with_backoff(do_scrape_sec)
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
        push_to_kv("sectors_performance", data)
    except Exception as e:
        print("Failed to scrape sector matrix after retries:", e)

    print("Scraping industry performance matrix...")
    def do_scrape_ind():
        fgoverview = GroupOverview()
        return fgoverview.screener_view(group="Industry")

    try:
        df = retry_with_backoff(do_scrape_ind)
        data = []
        if df is not None:
            df = df.fillna("")
            data = df.to_dict(orient="records")
        push_to_kv("industries_performance", data)
    except Exception as e:
        print("Failed to scrape industry matrix after retries:", e)

def sync_reddit():
    print("Scraping Reddit and WSB stock sentiment...")
    def do_fetch():
        res = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks", headers=get_random_headers(), timeout=10)
        res.raise_for_status()
        return res

    try:
        res = retry_with_backoff(do_fetch)
        payload = res.json()
        data = payload.get("results", [])
        push_to_kv("reddit_sentiment", data)
    except Exception as e:
        print("Failed to sync Reddit sentiment after retries:", e)

def process_turbulence_output(df_result):
    # Pre-calculate raw and smoothed position sizes for all dates
    # P0-5: Warning levels correspond to Level I-IV, with dynamic cap scaling down to 0%.
    raw_positions = []
    for idx, row in df_result.iterrows():
        v_comp = row['vix_level'] < row['vix_dynamic_threshold']
        m_comp = row['move_level'] < row['move_dynamic_threshold']
        c_comp = row['credit_ratio'] < row['credit_dynamic_threshold']
        any_comp = bool(sum([v_comp, m_comp, c_comp]) >= 2)

        c_stressed = bool(row['credit_ratio'] > (row['credit_rolling_mean'] + 1.5 * row['credit_rolling_std']))

        h_warn = row['macro_warn']
        h_extreme = row['macro_extreme']
        h_macro_slow = row['macro_slow']
        if h_extreme > h_warn:
            hx = (h_macro_slow - h_warn) / (h_extreme - h_warn)
        else:
            hx = 0.0

        prob = float(row['probit_prob'])
        st_type = str(row['steepening_type'])
        sos = float(row['sos_indicator'])
        
        # Calculate daily state
        daily_state = "NORMAL"
        if h_macro_slow > h_extreme or sos >= 0.20:
            daily_state = "CRITICAL"
        elif prob > 0.50 or st_type == 'BULL_STEEPENER' or sos >= 0.15:
            daily_state = "HIGH RISK"
        elif prob > 0.30 or row['net_liq_z'] < 0 or row['sofr_iorb_spread'] > 0 or h_macro_slow > h_warn or c_stressed:
            daily_state = "ELEVATED RISK"

        # Calculate position using standard sigmoid
        raw_pos = calculate_sigmoid_position(hx, any_comp, c_stressed, prob > 0.30)
        
        # Dynamic caps based on macro warning levels
        if daily_state == "CRITICAL":
            raw_pos = 0.0
        elif daily_state == "HIGH RISK":
            raw_pos = min(raw_pos, 25.0)
            if prob > 0:
                raw_pos = min(raw_pos, 100.0 * (1.0 - prob))
        elif daily_state == "ELEVATED RISK":
            raw_pos = min(raw_pos, 50.0)
            if prob > 0:
                raw_pos = min(raw_pos, 100.0 * (1.0 - prob))
                
        raw_positions.append(raw_pos)

    df_result['position_raw'] = raw_positions
    df_result['position_smoothed'] = df_result['position_raw'].ewm(span=5, adjust=False).mean()

    latest = df_result.iloc[-1]

    macro_above_warn = bool(latest['macro_slow'] > latest['macro_warn'])
    sector_above_warn = bool(latest['sector_slow'] > latest['sector_warn'])
    spx_above_sma50 = bool(latest['spx_level'] > latest['spx_sma50'] * 1.01)

    vix_complacent = bool(latest['vix_level'] < latest['vix_dynamic_threshold'])
    move_complacent = bool(latest['move_level'] < latest['move_dynamic_threshold'])
    credit_complacent = bool(latest['credit_ratio'] < latest['credit_dynamic_threshold'])

    any_complacency = bool(sum([vix_complacent, move_complacent, credit_complacent]) >= 2)

    credit_stressed = bool(latest['credit_ratio'] > (latest['credit_rolling_mean'] + 1.5 * latest['credit_rolling_std']))

    # P0-5: Multi-dimensional Warning Level mapping
    probit_prob = float(latest['probit_prob'])
    sos_indicator = float(latest['sos_indicator'])
    steepening_type = str(latest['steepening_type'])
    
    state = "NORMAL"
    if latest['macro_slow'] > latest['macro_extreme'] or sos_indicator >= 0.20:
        state = "CRITICAL"
    elif probit_prob > 0.50 or steepening_type == 'BULL_STEEPENER' or sos_indicator >= 0.15:
        state = "HIGH RISK"
    elif probit_prob > 0.30 or latest['net_liq_z'] < 0 or latest['sofr_iorb_spread'] > 0 or macro_above_warn or sector_above_warn or credit_stressed:
        state = "ELEVATED RISK"

    state_flags = {
        "normal": state == "NORMAL",
        "elevated": state == "ELEVATED RISK",
        "high_risk": state == "HIGH RISK",
        "critical": state == "CRITICAL"
    }
        
    state_colors = {
        "NORMAL": "#2ec4b6",
        "ELEVATED RISK": "#ffbf00",
        "HIGH RISK": "#d98a2b",
        "CRITICAL": "#e71d36"
    }
    
    position_size_pct = int(round(latest['position_smoothed'])) if not pd.isna(latest['position_smoothed']) else 100
    
    chart_series = []
    for _, row in df_result.iterrows():
        c_stressed = bool(row['credit_ratio'] > (row['credit_rolling_mean'] + 1.5 * row['credit_rolling_std']))

        chart_series.append({
            "date": row['date'],
            "turb_slow": round(float(row['macro_slow']), 2),
            "turb_fast": round(float(row['macro_fast']), 2),
            "slow_warn": round(float(row['macro_warn']), 2),
            "slow_extreme": round(float(row['macro_extreme']), 2),
            "macro_slow": round(float(row['macro_slow']), 2),
            "macro_fast": round(float(row['macro_fast']), 2),
            "macro_warn": round(float(row['macro_warn']), 2),
            "macro_extreme": round(float(row['macro_extreme']), 2),
            "sector_slow": round(float(row['sector_slow']), 2),
            "sector_fast": round(float(row['sector_fast']), 2),
            "sector_warn": round(float(row['sector_warn']), 2),
            "sector_extreme": round(float(row['sector_extreme']), 2),
            "spx": round(float(row['spx_level']), 2),
            "vix": round(float(row['vix_level']), 2),
            "vix_rolling_mean": round(float(row['vix_rolling_mean']), 2),
            "vix_dynamic_threshold": round(float(row['vix_dynamic_threshold']), 2),
            "move": round(float(row['move_level']), 2),
            "move_rolling_mean": round(float(row['move_rolling_mean']), 2),
            "move_dynamic_threshold": round(float(row['move_dynamic_threshold']), 2),
            "credit_ratio": round(float(row['credit_ratio']), 3),
            "credit_dynamic_threshold": round(float(row['credit_dynamic_threshold']), 3),
            "danger_zone": bool(row['probit_warning']),  # kept key for frontend compat
            "credit_stressed": c_stressed,
            "position_size_pct": int(round(row['position_smoothed'])) if not pd.isna(row['position_smoothed']) else 100,
            "probit_prob": round(float(row['probit_prob']), 4),
            "probit_warning": bool(row['probit_warning']),
            # P0-5: Add macro plumbing & labor indicators to chart
            "net_liq": round(float(row['net_liq']), 2),
            "net_liq_z": round(float(row['net_liq_z']), 3),
            "sofr": round(float(row['sofr']), 3),
            "iorb": round(float(row['iorb']), 3),
            "sofr_iorb_spread": round(float(row['sofr_iorb_spread']), 3),
            "iursa": round(float(row['iursa']), 2),
            "icsa": int(row['icsa']) if not pd.isna(row['icsa']) else 0,
            "sos_indicator": round(float(row['sos_indicator']), 3),
            "steepening_type": str(row['steepening_type'])
        })

    # P0-4: Record Probit warning periods (probit_prob > 0.30)
    probit_periods = []
    in_period = False
    start_date = None
    peak_prob = 0.0

    for idx, row in df_result.iterrows():
        is_warning = bool(row['probit_warning'])

        if is_warning:
            if not in_period:
                in_period = True
                start_date = row['date']
                peak_prob = float(row['probit_prob'])
            else:
                peak_prob = max(peak_prob, float(row['probit_prob']))
        else:
            if in_period:
                end_date = df_result.iloc[idx-1]['date']
                probit_periods.append({
                    "start_date": start_date,
                    "end_date": end_date,
                    "peak_prob": round(peak_prob, 4),
                    "duration_days": int((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days) + 1
                })
                in_period = False

    if in_period:
        end_date = df_result.iloc[-1]['date']
        probit_periods.append({
            "start_date": start_date,
            "end_date": "Present",
            "peak_prob": round(peak_prob, 4),
            "duration_days": int((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days) + 1
        })

    probit_periods.reverse()
    danger_zone_history = probit_periods[:10]  # keep key name for frontend compat
    
    # Format Contributors
    macro_contribs_list = []
    tot_abs_macro = sum(abs(v) for v in latest['macro_contrib'].values()) or 1.0
    for ticker, val in latest['macro_contrib'].items():
        macro_contribs_list.append({
            "ticker": ticker,
            "contribution": round(val, 4),
            "pct": round((abs(val) / tot_abs_macro) * 100, 1),
            "return": round(latest['macro_returns'][ticker], 4)
        })
    macro_contribs_list = sorted(macro_contribs_list, key=lambda x: abs(x['contribution']), reverse=True)
    
    sector_contribs_list = []
    tot_abs_sector = sum(abs(v) for v in latest['sector_contrib'].values()) or 1.0
    for ticker, val in latest['sector_contrib'].items():
        sector_contribs_list.append({
            "ticker": ticker,
            "contribution": round(val, 4),
            "pct": round((abs(val) / tot_abs_sector) * 100, 1),
            "return": round(latest['sector_returns'][ticker], 4)
        })
    sector_contribs_list = sorted(sector_contribs_list, key=lambda x: abs(x['contribution']), reverse=True)
    
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": {
            "date": latest['date'],
            "state": state,
            "state_color": state_colors[state],
            "state_flags": state_flags,
            "position_size_pct": position_size_pct,
            "turbulence": {
                "slow": round(float(latest['macro_slow']), 2),
                "fast": round(float(latest['macro_fast']), 2),
                "warning_threshold": round(float(latest['macro_warn']), 2),
                "extreme_threshold": round(float(latest['macro_extreme']), 2),
                "cov_condition_number": round(float(latest['cov_cond_macro']), 2),
                "cov_healthy": bool(latest['cov_healthy_macro'])
            },
            "macro_turbulence": {
                "slow": round(float(latest['macro_slow']), 2),
                "fast": round(float(latest['macro_fast']), 2),
                "warning_threshold": round(float(latest['macro_warn']), 2),
                "extreme_threshold": round(float(latest['macro_extreme']), 2),
                "cov_condition_number": round(float(latest['cov_cond_macro']), 2),
                "cov_healthy": bool(latest['cov_healthy_macro'])
            },
            "sector_dispersion": {
                "slow": round(float(latest['sector_slow']), 2),
                "fast": round(float(latest['sector_fast']), 2),
                "warning_threshold": round(float(latest['sector_warn']), 2),
                "extreme_threshold": round(float(latest['sector_extreme']), 2),
                "cov_condition_number": round(float(latest['cov_cond_sector']), 2),
                "cov_healthy": bool(latest['cov_healthy_sector'])
            },
            "spx": {
                "level": round(float(latest['spx_level']), 2),
                "sma50": round(float(latest['spx_sma50']), 2),
                "above_sma50": spx_above_sma50
            },
            "vix": {
                "level": round(float(latest['vix_level']), 2),
                "below_25": bool(latest['vix_level'] < 25.0),
                "dynamic_threshold": round(float(latest['vix_dynamic_threshold']), 2),
                "rolling_mean": round(float(latest['vix_rolling_mean']), 2),
                "below_dynamic": vix_complacent
            },
            "move": {
                "level": round(float(latest['move_level']), 2),
                "dynamic_threshold": round(float(latest['move_dynamic_threshold']), 2),
                "rolling_mean": round(float(latest['move_rolling_mean']), 2),
                "below_dynamic": move_complacent
            },
            "credit": {
                "level": round(float(latest['credit_ratio']), 3),
                "dynamic_threshold": round(float(latest['credit_dynamic_threshold']), 3),
                "rolling_mean": round(float(latest['credit_rolling_mean']), 3),
                "below_dynamic": credit_complacent,
                "stressed": credit_stressed
            },
            "divergence": {
                "active": bool(latest['probit_warning'])  # P0-4: Probit-driven
            },
            "probit": {
                "probability": round(float(latest['probit_prob']), 4),
                "is_warning": bool(latest['probit_warning']),
                "z_value": round(float(latest['probit_z']), 4),
                "vix_raw": round(float(latest['vix_raw']), 4),
                "yc_raw": round(float(latest['yc_raw']), 4),
                "cs_raw": round(float(latest['cs_raw']), 4),
                "x_vix": round(float(latest['x_vix']), 4),
                "x_yc": round(float(latest['x_yc']), 4),
                "x_cs": round(float(latest['x_cs']), 4)
            },
            # P0-5: Add macro plumbing & labor indicators to status
            "macro_plumbing": {
                "walcl": round(float(latest['walcl']), 2),
                "tga": round(float(latest['tga']), 2),
                "rrp": round(float(latest['rrp']), 2),
                "net_liq": round(float(latest['net_liq']), 2),
                "net_liq_z_score": round(float(latest['net_liq_z']), 3),
                "sofr": round(float(latest['sofr']), 3),
                "iorb": round(float(latest['iorb']), 3),
                "sofr_iorb_spread": round(float(latest['sofr_iorb_spread']), 3),
                "steepening_type": str(latest['steepening_type'])
            },
            "labor": {
                "iursa": round(float(latest['iursa']), 3),
                "icsa": int(latest['icsa']) if not pd.isna(latest['icsa']) else 0,
                "sos_indicator": round(float(latest['sos_indicator']), 3),
                "sos_warning": bool(latest['sos_indicator'] >= 0.20)
            },
            "macro_contributors": macro_contribs_list,
            "sector_contributors": sector_contribs_list
        },
        "danger_zone_history": danger_zone_history,
        "chart_series": chart_series
    }
    return payload

def sync_turbulence():
    print("Syncing market turbulence index...")
    try:
        df_result = calculate_market_turbulence()
        payload = process_turbulence_output(df_result)
        push_to_kv("market_turbulence", payload, expires_in=172800) # 48 hours cache
        print("Market turbulence sync successful.")
    except Exception as e:
        print("Failed to sync market turbulence:", e)

def run_all_sync():
    sync_opportunities()
    sync_insiders()
    sync_sectors()
    sync_reddit()
    sync_turbulence()

if __name__ == "__main__":
    print("Starting local sync to Vercel KV...")
    run_all_sync()
    print("Sync completed successfully!")

