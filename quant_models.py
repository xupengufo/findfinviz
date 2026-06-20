import os
import io
import time
import random
import requests
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone

MACRO_TICKERS = ["SPY", "IWM", "EFA", "EEM", "TLT", "IEF", "HYG", "UUP", "GLD", "DBC"]
SECTOR_TICKERS = ["XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLB", "XLU", "XLRE", "XLC"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 OPR/108.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

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

def fetch_fred_csv(series_id):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    # Download with retry
    def do_request():
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        return res
    res = retry_with_backoff(do_request)
    df = pd.read_csv(io.StringIO(res.text), na_values=['.'])
    if 'observation_date' in df.columns:
        df['DATE'] = pd.to_datetime(df['observation_date'])
    elif 'DATE' in df.columns:
        df['DATE'] = pd.to_datetime(df['DATE'])
    else:
        raise KeyError(f"Date column not found in FRED series {series_id}")
    df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
    df = df.dropna().rename(columns={series_id: 'value'})
    df = df.set_index('DATE')
    return df

def get_ew_cov_and_mean(history, halflife=63):
    """Calculate exponentially weighted mean and covariance matrix."""
    N, k = history.shape
    weights = 2.0 ** (-np.arange(N - 1, -1, -1) / halflife)
    weights /= weights.sum()
    
    # Weighted mean
    weighted_mean = np.sum(history.values * weights[:, np.newaxis], axis=0)
    centered = history.values - weighted_mean
    
    # Divisor for unbiased weighted covariance
    divisor = 1.0 - np.sum(weights ** 2)
    if divisor <= 0:
        divisor = 1.0
        
    cov_matrix = (centered.T * weights) @ centered / divisor
    return weighted_mean, cov_matrix

def calculate_sigmoid_position(x, any_complacency, credit_stressed=False, probit_warning=False):
    """Map normalized distance x to a target position size using a smooth sigmoid.
    P0-4: removed danger_zone_active — risk state is now purely Probit-driven."""
    if any_complacency or credit_stressed or probit_warning:
        min_pos = 25.0
    else:
        min_pos = 50.0

    x_clipped = np.clip(x, -2.0, 5.0)
    sigmoid_val = 1.0 / (1.0 + np.exp(-4.0 * (x_clipped - 0.5)))

    pos = min_pos + (100.0 - min_pos) * (1.0 - sigmoid_val)
    return pos

def calculate_market_turbulence():
    print("Fetching historical data for Macro + Sector ETFs + Volatility indexes...")
    all_tickers = list(set(MACRO_TICKERS + SECTOR_TICKERS + ["^VIX", "^MOVE", "LQD", "HYG", "^TNX", "^IRX", "IEF"]))
    
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
    
    # Fetch historical FRED macro series and align
    print("Fetching historical FRED macro series...")
    fred_series = ["WALCL", "WDTGAL", "RRPONTTLD", "SOFR", "IORB", "IURSA", "ICSA"]
    fred_dfs = {}
    for sid in fred_series:
        try:
            fred_dfs[sid] = fetch_fred_csv(sid)
        except Exception as fe:
            print(f"Warning: Failed to fetch FRED series {sid}: {fe}. Using fallback mock data.")
            mock_dates = pd.date_range(start="2016-01-01", end=pd.Timestamp.now().normalize(), freq='D')
            mock_val = 0.0
            if sid == "WALCL": mock_val = 6700000.0
            elif sid == "WDTGAL": mock_val = 800000.0
            elif sid == "RRPONTTLD": mock_val = 10.0
            elif sid == "SOFR" or sid == "IORB": mock_val = 3.5
            elif sid == "IURSA": mock_val = 1.2
            elif sid == "ICSA": mock_val = 220000.0
            mock_df = pd.DataFrame({'value': mock_val}, index=mock_dates)
            fred_dfs[sid] = mock_df

    df_fred = pd.DataFrame(index=df_prices.index)
    for sid in fred_series:
        union_index = df_prices.index.union(fred_dfs[sid].index)
        df_fred[sid] = fred_dfs[sid]['value'].reindex(union_index).ffill().bfill().reindex(df_prices.index)
        
    # Calculate Net Liquidity (Billions)
    df_fred['net_liq'] = df_fred['WALCL'] / 1000.0 - df_fred['WDTGAL'] / 1000.0 - df_fred['RRPONTTLD']
    net_liq_mean = df_fred['net_liq'].rolling(504, min_periods=100).mean()
    net_liq_std = df_fred['net_liq'].rolling(504, min_periods=100).std().clip(lower=1.0)
    df_fred['net_liq_z'] = (df_fred['net_liq'] - net_liq_mean) / net_liq_std
    df_fred['net_liq_z'] = df_fred['net_liq_z'].fillna(0.0)
    
    # SOFR-IORB spread
    df_fred['sofr_iorb_spread'] = df_fred['SOFR'] - df_fred['IORB']
    
    # SOS Labor indicator
    iursa_ma26 = df_fred['IURSA'].rolling(26 * 7, min_periods=100).mean()
    iursa_min52 = df_fred['IURSA'].rolling(52 * 7, min_periods=252).min()
    df_fred['sos_indicator'] = iursa_ma26 - iursa_min52
    df_fred['sos_indicator'] = df_fred['sos_indicator'].fillna(0.0)
    
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
            if cov_healthy_macro:
                inv_cov_macro = np.linalg.inv(cov_macro)
                dev_macro = r_macro - mu_macro
                d2_macro = dev_macro @ inv_cov_macro @ dev_macro
                turb_macro = d2_macro / n_macro
                
                contrib_raw_macro = dev_macro * (inv_cov_macro @ dev_macro)
                denom_macro = d2_macro if d2_macro > 0 else 1.0
                contrib_pct_macro = contrib_raw_macro / denom_macro
            else:
                turb_macro = 1.0
                contrib_pct_macro = np.ones(n_macro) / n_macro
        except:
            turb_macro = 1.0
            contrib_pct_macro = np.ones(n_macro) / n_macro
            
        # Calculate Sector MD and contributions
        try:
            if cov_healthy_sector:
                inv_cov_sector = np.linalg.inv(cov_sector)
                dev_sector = r_sector - mu_sector
                d2_sector = dev_sector @ inv_cov_sector @ dev_sector
                turb_sector = d2_sector / n_sector
                
                contrib_raw_sector = dev_sector * (inv_cov_sector @ dev_sector)
                denom_sector = d2_sector if d2_sector > 0 else 1.0
                contrib_pct_sector = contrib_raw_sector / denom_sector
            else:
                turb_sector = 1.0
                contrib_pct_sector = np.ones(n_sector) / n_sector
        except:
            turb_sector = 1.0
            contrib_pct_sector = np.ones(n_sector) / n_sector
            
        turb_records.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "turb_macro_raw": turb_macro,
            "turb_sector_raw": turb_sector,
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
            "macro_contrib": {ticker: float(val) for ticker, val in zip(MACRO_TICKERS, contrib_pct_macro)},
            "sector_contrib": {ticker: float(val) for ticker, val in zip(SECTOR_TICKERS, contrib_pct_sector)},
            "macro_returns": {ticker: float(val) for ticker, val in zip(MACRO_TICKERS, r_macro)},
            "sector_returns": {ticker: float(val) for ticker, val in zip(SECTOR_TICKERS, r_sector)},
            # FRED values
            "walcl": float(df_fred.loc[current_date, 'WALCL']),
            "tga": float(df_fred.loc[current_date, 'WDTGAL']),
            "rrp": float(df_fred.loc[current_date, 'RRPONTTLD']),
            "net_liq": float(df_fred.loc[current_date, 'net_liq']),
            "net_liq_z": float(df_fred.loc[current_date, 'net_liq_z']),
            "sofr": float(df_fred.loc[current_date, 'SOFR']),
            "iorb": float(df_fred.loc[current_date, 'IORB']),
            "sofr_iorb_spread": float(df_fred.loc[current_date, 'sofr_iorb_spread']),
            "iursa": float(df_fred.loc[current_date, 'IURSA']),
            "icsa": float(df_fred.loc[current_date, 'ICSA']),
            "sos_indicator": float(df_fred.loc[current_date, 'sos_indicator'])
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
    
    # Standardize features using rolling fit parameters (504 trading days, approx 2 years)
    vix_fit_mean = df_result['vix_raw'].rolling(504, min_periods=252).mean()
    vix_fit_std  = df_result['vix_raw'].rolling(504, min_periods=252).std()
    yc_fit_mean  = df_result['yc_raw'].rolling(504, min_periods=252).mean()
    yc_fit_std   = df_result['yc_raw'].rolling(504, min_periods=252).std()
    cs_fit_mean  = df_result['cs_raw'].rolling(504, min_periods=252).mean()
    cs_fit_std   = df_result['cs_raw'].rolling(504, min_periods=252).std()

    # Fallback to the original static parameters for the initial periods where rolling is not fully populated
    vix_fit_mean = vix_fit_mean.fillna(19.824264)
    vix_fit_std  = vix_fit_std.fillna(8.345408)
    yc_fit_mean  = yc_fit_mean.fillna(1.433514)
    yc_fit_std   = yc_fit_std.fillna(1.282213)
    cs_fit_mean  = cs_fit_mean.fillna(4.736405)
    cs_fit_std   = cs_fit_std.fillna(0.762430)

    # Use fillna + clip to protect against zero variance or NaNs
    df_result['x_vix'] = ((df_result['vix_raw'] - vix_fit_mean) / vix_fit_std.clip(lower=1.0)).fillna(0)
    df_result['x_yc']  = ((df_result['yc_raw'] - yc_fit_mean) / yc_fit_std.clip(lower=0.1)).fillna(0)
    df_result['x_cs']  = ((df_result['cs_raw'] - cs_fit_mean) / cs_fit_std.clip(lower=0.1)).fillna(0)
    
    # Linear activation
    df_result['probit_z'] = 0.586576 * df_result['x_vix'] + 0.314905 * df_result['x_yc'] - 0.196963 * df_result['x_cs'] - 2.714673
    
    # Sigmoid function maps linear combination to [0, 1] probability
    df_result['probit_prob'] = 1.0 / (1.0 + np.exp(-df_result['probit_z']))
    df_result['probit_warning'] = df_result['probit_prob'] > 0.30
    
    # Yield curve steepening classification (20-day changes)
    df_result['yc_change_20d'] = df_result['yc_raw'] - df_result['yc_raw'].shift(20)
    df_result['irx_change_20d'] = df_result['irx_level'] - df_result['irx_level'].shift(20)
    df_result['tnx_change_20d'] = df_result['tnx_level'] - df_result['tnx_level'].shift(20)
    
    steepening_list = []
    for idx, row in df_result.iterrows():
        chg = row['yc_change_20d']
        irx_chg = row['irx_change_20d']
        tnx_chg = row['tnx_change_20d']
        if pd.isna(chg):
            steepening_list.append("NORMAL")
        elif chg > 0.10: # steepened by >10bps
            if irx_chg < 0:
                steepening_list.append("BULL_STEEPENER")
            elif tnx_chg > 0:
                steepening_list.append("BEAR_STEEPENER")
            else:
                steepening_list.append("NORMAL")
        else:
            steepening_list.append("NORMAL")
            
    df_result['steepening_type'] = steepening_list
    
    return df_result
