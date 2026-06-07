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

TURB_TICKERS = [
    "XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLB", "XLU", "XLRE", "XLC",
    "TLT", "IEF", "SHY",
    "GLD", "DBC",
    "EFA", "EEM"
]

def calculate_market_turbulence():
    print("Fetching historical data for 18 ETFs + SPY + VIX...")
    all_tickers = TURB_TICKERS + ["SPY", "^VIX"]
    
    def do_download():
        df = yf.download(all_tickers, period="3y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            if 'Adj Close' in df.columns.levels[0]:
                return df['Adj Close']
            elif 'Close' in df.columns.levels[0]:
                return df['Close']
        return df
        
    df_prices = retry_with_backoff(do_download)
    df_prices = df_prices.ffill().bfill().dropna()
    
    df_returns = df_prices[TURB_TICKERS].pct_change().dropna()
    spy_series = df_prices["SPY"]
    vix_series = df_prices["^VIX"]
    spy_sma50 = spy_series.rolling(window=50).mean()
    
    turb_records = []
    dates = df_returns.index
    n_assets = len(TURB_TICKERS)
    
    for i in range(252, len(df_returns)):
        current_date = dates[i]
        r_t = df_returns.iloc[i].values
        history = df_returns.iloc[i-252:i]
        mu = history.mean().values
        cov = history.cov().values
        
        # Calculate condition number of covariance matrix
        cond_num = np.linalg.cond(cov)
        cov_healthy = bool(cond_num < 1000)
        
        try:
            cov_inv = np.linalg.pinv(cov)
            diff = r_t - mu
            d_t = float(diff.T @ cov_inv @ diff) / n_assets
        except Exception as e:
            d_t = np.nan
            cov_healthy = False
            
        turb_records.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "turb_raw": d_t,
            "cov_condition_number": float(cond_num) if not np.isinf(cond_num) and not np.isnan(cond_num) else 999999.0,
            "cov_healthy": cov_healthy,
            "spx_level": float(spy_series.loc[current_date]),
            "spx_sma50": float(spy_sma50.loc[current_date]) if not np.isnan(spy_sma50.loc[current_date]) else float(spy_series.loc[current_date]),
            "vix_level": float(vix_series.loc[current_date])
        })
        
    df_result = pd.DataFrame(turb_records)
    df_result['turb_slow'] = df_result['turb_raw'].ewm(span=5, adjust=False).mean()
    df_result['turb_fast'] = df_result['turb_raw'].ewm(span=2, adjust=False).mean()
    
    # Calculate 504 trading days rolling percentile (2 years)
    df_result['slow_warn'] = df_result['turb_slow'].rolling(504, min_periods=100).quantile(0.95)
    df_result['slow_extreme'] = df_result['turb_slow'].rolling(504, min_periods=100).quantile(0.99)
    
    # Handle NaN values
    df_result['slow_warn'] = df_result['slow_warn'].ffill().bfill()
    df_result['slow_extreme'] = df_result['slow_extreme'].ffill().bfill()
    
    # Fallback default values
    df_result['slow_warn'] = df_result['slow_warn'].fillna(2.0)
    df_result['slow_extreme'] = df_result['slow_extreme'].fillna(4.0)
    
    return df_result

def process_turbulence_output(df_result):
    latest = df_result.iloc[-1]
    
    turb_above_warn = bool(latest['turb_slow'] > latest['slow_warn'])
    spx_above_sma50 = bool(latest['spx_level'] > latest['spx_sma50'])
    vix_complacent = bool(latest['vix_level'] < 25.0)
    
    danger_zone_active = bool(turb_above_warn and spx_above_sma50 and vix_complacent)
    
    state = "NORMAL"
    if latest['turb_slow'] > latest['slow_extreme'] and vix_complacent:
        state = "CRITICAL"
    elif danger_zone_active:
        state = "HIGH RISK"
    elif turb_above_warn:
        state = "ELEVATED RISK"
        
    state_colors = {
        "NORMAL": "#2ec4b6",
        "ELEVATED RISK": "#ffbf00",
        "HIGH RISK": "#d98a2b",
        "CRITICAL": "#e71d36"
    }
    
    chart_series = []
    for _, row in df_result.iterrows():
        t_warn = row['turb_slow'] > row['slow_warn']
        s_above = row['spx_level'] > row['spx_sma50']
        v_comp = row['vix_level'] < 25.0
        dz = bool(t_warn and s_above and v_comp)
        
        chart_series.append({
            "date": row['date'],
            "turb_slow": round(float(row['turb_slow']), 2),
            "turb_fast": round(float(row['turb_fast']), 2),
            "slow_warn": round(float(row['slow_warn']), 2),
            "slow_extreme": round(float(row['slow_extreme']), 2),
            "spx": round(float(row['spx_level']), 2),
            "vix": round(float(row['vix_level']), 2),
            "danger_zone": dz
        })
        
    position_size_pct = 100
    if state == "ELEVATED RISK":
        position_size_pct = 75
    elif state == "HIGH RISK":
        position_size_pct = 50
    elif state == "CRITICAL":
        position_size_pct = 25
        
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": {
            "date": latest['date'],
            "state": state,
            "state_color": state_colors[state],
            "position_size_pct": position_size_pct,
            "turbulence": {
                "slow": round(float(latest['turb_slow']), 2),
                "fast": round(float(latest['turb_fast']), 2),
                "warning_threshold": round(float(latest['slow_warn']), 2),
                "extreme_threshold": round(float(latest['slow_extreme']), 2),
                "cov_condition_number": round(float(latest['cov_condition_number']), 2),
                "cov_healthy": bool(latest['cov_healthy'])
            },
            "spx": {
                "level": round(float(latest['spx_level']), 2),
                "sma50": round(float(latest['spx_sma50']), 2),
                "above_sma50": spx_above_sma50
            },
            "vix": {
                "level": round(float(latest['vix_level']), 2),
                "below_25": vix_complacent
            },
            "divergence": {
                "active": danger_zone_active
            }
        },
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

