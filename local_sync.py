import os
import sys
import json
import time
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

def retry_with_backoff(func, max_retries=3, base_delay=2):
    """Execute a function with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            print(f"  Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)

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
    signals = {
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
        "quality_compounder": "quality_compounder",
        "overbought": "Overbought",
        "wedge_up": "Wedge Up",
        "wedge_down": "Wedge Down"
    }
    
    for key, signal_name in signals.items():
        print(f"Scraping opportunities for signal: {signal_name}...")

        def do_scrape(sig_key=key, sig_val=signal_name):
            fcustom = Custom()
            if sig_key == "high_short_interest":
                fcustom.set_filter(filters_dict={"Float Short": "Over 15%"})
            elif sig_key == "pullback":
                fcustom.set_filter(filters_dict={
                    "50-Day Simple Moving Average": "Price above SMA50",
                    "200-Day Simple Moving Average": "Price above SMA200",
                    "RSI (14)": "Not Overbought (<50)"
                })
            elif sig_key == "breakout_candidate":
                fcustom.set_filter(filters_dict={
                    "52-Week High/Low": "0-5% below High",
                    "Relative Volume": "Over 1.5"
                })
            elif sig_key == "quality_compounder":
                fcustom.set_filter(filters_dict={
                    "Return on Equity": "Over +15%",
                    "Debt/Equity": "Under 1",
                    "P/E": "Profitable (>0)"
                })
            else:
                fcustom.set_filter(signal=sig_val)
            return fcustom.screener_view(
                limit=100, 
                order="Market Cap.", 
                ascend=False, 
                verbose=0, 
                columns=[0, 1, 2, 3, 4, 6, 7, 30, 33, 38, 64, 65, 66, 67]
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
        res = requests.get("https://apewisdom.io/api/v1.0/filter/all-stocks", timeout=10)
        res.raise_for_status()
        return res

    try:
        res = retry_with_backoff(do_fetch)
        payload = res.json()
        data = payload.get("results", [])
        push_to_kv("reddit_sentiment", data)
    except Exception as e:
        print("Failed to sync Reddit sentiment after retries:", e)

def get_ew_cov_and_mean(history, halflife=63):
    """Calculate exponentially weighted mean and covariance matrix."""
    N, k = history.shape
    weights = 2.0 ** (-np.arange(N - 1, -1, -1) / halflife)
    weights /= weights.sum()
    
    # Weighted mean
    weighted_mean = np.sum(history.values * weights[:, np.newaxis], axis=0)
    
    # Centered returns
    centered = history.values - weighted_mean
    
    # Unbiased weighted covariance
    divisor = 1.0 - np.sum(weights ** 2)
    if divisor <= 0:
        divisor = 1.0
    cov_matrix = (centered.T * weights) @ centered / divisor
    
    return weighted_mean, cov_matrix

def calculate_sigmoid_position(x, danger_zone_active, any_complacency, credit_stressed=False, probit_warning=False):
    """Map normalized distance x to a target position size using a smooth sigmoid."""
    if danger_zone_active or any_complacency or credit_stressed or probit_warning:
        min_pos = 25.0
    else:
        min_pos = 50.0
        
    x_clipped = np.clip(x, -2.0, 5.0)
    sigmoid_val = 1.0 / (1.0 + np.exp(-4.0 * (x_clipped - 0.5)))
    
    pos = min_pos + (100.0 - min_pos) * (1.0 - sigmoid_val)
    return pos

MACRO_TICKERS = ["SPY", "IWM", "EFA", "EEM", "TLT", "IEF", "HYG", "UUP", "GLD", "DBC"]
SECTOR_TICKERS = ["XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLB", "XLU", "XLRE", "XLC"]

def calculate_market_turbulence():
    print("Fetching historical data for Macro + Sector ETFs + Volatility indexes...")
    all_tickers = list(set(MACRO_TICKERS + SECTOR_TICKERS + ["^VIX", "^MOVE", "LQD", "^TNX", "^IRX"]))
    
    def do_download():
        df = yf.download(all_tickers, period="10y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            if 'Adj Close' in df.columns.levels[0]:
                return df['Adj Close']
            elif 'Close' in df.columns.levels[0]:
                return df['Close']
        return df
        
    df_prices = retry_with_backoff(do_download)
    df_prices = df_prices.ffill().bfill().dropna()
    
    df_returns_macro = df_prices[MACRO_TICKERS].pct_change().dropna()
    df_returns_sector = df_prices[SECTOR_TICKERS].pct_change().dropna()
    
    spy_series = df_prices["SPY"]
    vix_series = df_prices["^VIX"]
    move_series = df_prices["^MOVE"]
    lqd_series = df_prices["LQD"]
    hyg_series = df_prices["HYG"]
    tnx_series = df_prices["^TNX"]
    irx_series = df_prices["^IRX"]
    ief_series = df_prices["IEF"]
    
    spy_sma50 = spy_series.rolling(window=50).mean()
    
    # Calculate rolling VIX metrics
    vix_rolling_mean = vix_series.rolling(window=252, min_periods=100).mean()
    vix_rolling_std = vix_series.rolling(window=252, min_periods=100).std()
    vix_rolling_mean = vix_rolling_mean.ffill().bfill().fillna(20.0)
    vix_rolling_std = vix_rolling_std.ffill().bfill().fillna(4.0)
    vix_dynamic_threshold = np.clip(vix_rolling_mean + vix_rolling_std, 18.0, 28.0)
    
    # Calculate rolling MOVE metrics
    move_rolling_mean = move_series.rolling(window=252, min_periods=100).mean()
    move_rolling_std = move_series.rolling(window=252, min_periods=100).std()
    move_rolling_mean = move_rolling_mean.ffill().bfill().fillna(80.0)
    move_rolling_std = move_rolling_std.ffill().bfill().fillna(15.0)
    move_dynamic_threshold = np.clip(move_rolling_mean + move_rolling_std, 70.0, 120.0)
    
    # Calculate Credit Ratio (LQD / HYG)
    credit_ratio = lqd_series / hyg_series
    credit_rolling_mean = credit_ratio.rolling(window=252, min_periods=100).mean()
    credit_rolling_std = credit_ratio.rolling(window=252, min_periods=100).std()
    credit_rolling_mean = credit_rolling_mean.ffill().bfill().fillna(1.35)
    credit_rolling_std = credit_rolling_std.ffill().bfill().fillna(0.05)
    credit_dynamic_threshold = credit_rolling_mean + credit_rolling_std
    
    dates = df_returns_macro.index.intersection(df_returns_sector.index)
    df_returns_macro = df_returns_macro.loc[dates]
    df_returns_sector = df_returns_sector.loc[dates]
    
    turb_records = []
    n_macro = len(MACRO_TICKERS)
    n_sector = len(SECTOR_TICKERS)
    
    for i in range(252, len(dates)):
        current_date = dates[i]
        
        # 1. Macro calculation
        r_macro = df_returns_macro.iloc[i].values
        history_macro = df_returns_macro.iloc[i-252:i]
        mu_macro, cov_macro = get_ew_cov_and_mean(history_macro, halflife=63)
        
        cond_macro = np.linalg.cond(cov_macro)
        cov_healthy_macro = bool(cond_macro < 1000)
        
        # 2. Sector calculation
        r_sector = df_returns_sector.iloc[i].values
        history_sector = df_returns_sector.iloc[i-252:i]
        mu_sector, cov_sector = get_ew_cov_and_mean(history_sector, halflife=63)
        
        cond_sector = np.linalg.cond(cov_sector)
        cov_healthy_sector = bool(cond_sector < 1000)
        
        # Calculate Macro MD and contributions
        try:
            cov_inv_macro = np.linalg.pinv(cov_macro)
            diff_macro = r_macro - mu_macro
            d_macro = float(diff_macro.T @ cov_inv_macro @ diff_macro) / n_macro
            w_macro = cov_inv_macro @ diff_macro
            contribs_macro = (diff_macro * w_macro) / n_macro
        except:
            d_macro = np.nan
            contribs_macro = np.zeros(n_macro)
            cov_healthy_macro = False
            
        # Calculate Sector MD and contributions
        try:
            cov_inv_sector = np.linalg.pinv(cov_sector)
            diff_sector = r_sector - mu_sector
            d_sector = float(diff_sector.T @ cov_inv_sector @ diff_sector) / n_sector
            w_sector = cov_inv_sector @ diff_sector
            contribs_sector = (diff_sector * w_sector) / n_sector
        except:
            d_sector = np.nan
            contribs_sector = np.zeros(n_sector)
            cov_healthy_sector = False
            
        macro_contrib_dict = {ticker: float(val) for ticker, val in zip(MACRO_TICKERS, contribs_macro)}
        sector_contrib_dict = {ticker: float(val) for ticker, val in zip(SECTOR_TICKERS, contribs_sector)}
        
        macro_ret_dict = {ticker: float(val) for ticker, val in zip(MACRO_TICKERS, r_macro)}
        sector_ret_dict = {ticker: float(val) for ticker, val in zip(SECTOR_TICKERS, r_sector)}
        
        turb_records.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "turb_macro_raw": d_macro,
            "turb_sector_raw": d_sector,
            "cov_cond_macro": float(cond_macro) if not np.isinf(cond_macro) and not np.isnan(cond_macro) else 999999.0,
            "cov_cond_sector": float(cond_sector) if not np.isinf(cond_sector) and not np.isnan(cond_sector) else 999999.0,
            "cov_healthy_macro": cov_healthy_macro,
            "cov_healthy_sector": cov_healthy_sector,
            "spx_level": float(spy_series.loc[current_date]),
            "spx_sma50": float(spy_sma50.loc[current_date]) if not np.isnan(spy_sma50.loc[current_date]) else float(spy_series.loc[current_date]),
            "vix_level": float(vix_series.loc[current_date]),
            "vix_rolling_mean": float(vix_rolling_mean.loc[current_date]),
            "vix_dynamic_threshold": float(vix_dynamic_threshold.loc[current_date]),
            "move_level": float(move_series.loc[current_date]) if current_date in move_series.index and not np.isnan(move_series.loc[current_date]) else 80.0,
            "move_rolling_mean": float(move_rolling_mean.loc[current_date]),
            "move_dynamic_threshold": float(move_dynamic_threshold.loc[current_date]),
            "credit_ratio": float(credit_ratio.loc[current_date]),
            "credit_rolling_mean": float(credit_rolling_mean.loc[current_date]),
            "credit_rolling_std": float(credit_rolling_std.loc[current_date]),
            "credit_dynamic_threshold": float(credit_dynamic_threshold.loc[current_date]),
            "tnx_level": float(tnx_series.loc[current_date]),
            "irx_level": float(irx_series.loc[current_date]),
            "ief_level": float(ief_series.loc[current_date]),
            "hyg_level": float(hyg_series.loc[current_date]),
            "macro_contrib": macro_contrib_dict,
            "sector_contrib": sector_contrib_dict,
            "macro_returns": macro_ret_dict,
            "sector_returns": sector_ret_dict
        })
        
    df_result = pd.DataFrame(turb_records)
    df_result['macro_slow'] = df_result['turb_macro_raw'].ewm(span=15, adjust=False).mean()
    df_result['macro_fast'] = df_result['turb_macro_raw'].ewm(span=3, adjust=False).mean()
    df_result['sector_slow'] = df_result['turb_sector_raw'].ewm(span=15, adjust=False).mean()
    df_result['sector_fast'] = df_result['turb_sector_raw'].ewm(span=3, adjust=False).mean()
    
    df_result['macro_warn'] = df_result['macro_slow'].rolling(504, min_periods=100).quantile(0.95)
    df_result['macro_extreme'] = df_result['macro_slow'].rolling(504, min_periods=100).quantile(0.99)
    df_result['sector_warn'] = df_result['sector_slow'].rolling(504, min_periods=100).quantile(0.95)
    df_result['sector_extreme'] = df_result['sector_slow'].rolling(504, min_periods=100).quantile(0.99)
    
    df_result['macro_warn'] = df_result['macro_warn'].ffill().bfill().fillna(2.0)
    df_result['macro_extreme'] = df_result['macro_extreme'].ffill().bfill().fillna(4.0)
    df_result['sector_warn'] = df_result['sector_warn'].ffill().bfill().fillna(2.0)
    df_result['sector_extreme'] = df_result['sector_extreme'].ffill().bfill().fillna(4.0)
    
    # Calculate Probit Composite Warning Model features
    df_result['vix_raw'] = df_result['vix_level']
    df_result['yc_raw'] = df_result['tnx_level'] - df_result['irx_level']
    df_result['cs_raw'] = (df_result['ief_level'] / df_result['hyg_level']) * 3.0
    
    # Standardize features using the specified fitted mean and std parameters
    df_result['x_vix'] = (df_result['vix_raw'] - 19.824264) / 8.345408
    df_result['x_yc'] = (df_result['yc_raw'] - 1.433514) / 1.282213
    df_result['x_cs'] = (df_result['cs_raw'] - 4.736405) / 0.762430
    
    # Linear activation
    df_result['probit_z'] = 0.586576 * df_result['x_vix'] + 0.314905 * df_result['x_yc'] - 0.196963 * df_result['x_cs'] - 2.714673
    
    # Sigmoid function maps linear combination to [0, 1] probability
    df_result['probit_prob'] = 1.0 / (1.0 + np.exp(-df_result['probit_z']))
    df_result['probit_warning'] = df_result['probit_prob'] > 0.30
    
    return df_result

def process_turbulence_output(df_result):
    # Pre-calculate raw and smoothed position sizes for all dates
    raw_positions = []
    for _, row in df_result.iterrows():
        t_warn = row['macro_slow'] > row['macro_warn']
        s_disp_warn = row['sector_slow'] > row['sector_warn']
        s_above = row['spx_level'] > row['spx_sma50'] * 1.01
        
        v_comp = row['vix_level'] < row['vix_dynamic_threshold']
        m_comp = row['move_level'] < row['move_dynamic_threshold']
        c_comp = row['credit_ratio'] < row['credit_dynamic_threshold']
        any_comp = bool(sum([v_comp, m_comp, c_comp]) >= 2)
        
        dz = bool((t_warn or s_disp_warn) and s_above and any_comp)
        c_stressed = bool(row['credit_ratio'] > (row['credit_rolling_mean'] + 1.5 * row['credit_rolling_std']))
        
        h_warn = row['macro_warn']
        h_extreme = row['macro_extreme']
        h_macro_slow = row['macro_slow']
        if h_extreme > h_warn:
            hx = (h_macro_slow - h_warn) / (h_extreme - h_warn)
        else:
            hx = 0.0
            
        probit_warn = bool(row['probit_warning'])
        raw_pos = calculate_sigmoid_position(hx, dz, any_comp, c_stressed, probit_warn)
        if probit_warn:
            # Dynamic cap on position size based on crash probability
            probit_cap = 100.0 * (1.0 - float(row['probit_prob']))
            raw_pos = min(raw_pos, probit_cap)
            
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
    danger_zone_active = bool((macro_above_warn or sector_above_warn) and spx_above_sma50 and any_complacency)
    
    credit_stressed = bool(latest['credit_ratio'] > (latest['credit_rolling_mean'] + 1.5 * latest['credit_rolling_std']))
    
    state = "NORMAL"
    if latest['macro_slow'] > latest['macro_extreme']:
        state = "CRITICAL"
    elif danger_zone_active:
        state = "HIGH RISK"
    elif bool(latest['probit_warning']):
        if float(latest['probit_prob']) > 0.50:
            state = "HIGH RISK"
        else:
            state = "ELEVATED RISK"
    elif macro_above_warn or sector_above_warn or credit_stressed:
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
    
    position_size_pct = int(round(latest['position_smoothed']))
    
    chart_series = []
    for _, row in df_result.iterrows():
        t_warn = row['macro_slow'] > row['macro_warn']
        s_disp_warn = row['sector_slow'] > row['sector_warn']
        s_above = row['spx_level'] > row['spx_sma50'] * 1.01
        
        v_comp = row['vix_level'] < row['vix_dynamic_threshold']
        m_comp = row['move_level'] < row['move_dynamic_threshold']
        c_comp = row['credit_ratio'] < row['credit_dynamic_threshold']
        any_comp = bool(sum([v_comp, m_comp, c_comp]) >= 2)
        
        dz = bool((t_warn or s_disp_warn) and s_above and any_comp)
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
            "danger_zone": dz,
            "credit_stressed": c_stressed,
            "position_size_pct": int(round(row['position_smoothed'])),
            "probit_prob": round(float(row['probit_prob']), 4),
            "probit_warning": bool(row['probit_warning'])
        })
        
    dz_periods = []
    in_period = False
    start_date = None
    peak_turb = 0.0
    
    for idx, row in df_result.iterrows():
        t_warn = row['macro_slow'] > row['macro_warn']
        s_disp_warn = row['sector_slow'] > row['sector_warn']
        s_above = row['spx_level'] > row['spx_sma50'] * 1.01
        v_comp = row['vix_level'] < row['vix_dynamic_threshold']
        m_comp = row['move_level'] < row['move_dynamic_threshold']
        c_comp = row['credit_ratio'] < row['credit_dynamic_threshold']
        any_comp = bool(sum([v_comp, m_comp, c_comp]) >= 2)
        dz = bool((t_warn or s_disp_warn) and s_above and any_comp)
        
        if dz:
            if not in_period:
                in_period = True
                start_date = row['date']
                peak_turb = float(row['macro_slow'])
            else:
                peak_turb = max(peak_turb, float(row['macro_slow']))
        else:
            if in_period:
                end_date = df_result.iloc[idx-1]['date']
                dz_periods.append({
                    "start_date": start_date,
                    "end_date": end_date,
                    "peak_turb": round(peak_turb, 2),
                    "duration_days": int((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days) + 1
                })
                in_period = False
                
    if in_period:
        end_date = df_result.iloc[-1]['date']
        dz_periods.append({
            "start_date": start_date,
            "end_date": "Present",
            "peak_turb": round(peak_turb, 2),
            "duration_days": int((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days) + 1
        })
        
    dz_periods.reverse()
    danger_zone_history = dz_periods[:10]
    
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
                "active": danger_zone_active
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

