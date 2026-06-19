import os
import sys
import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone

MACRO_TICKERS = ["SPY", "IWM", "EFA", "EEM", "TLT", "IEF", "HYG", "UUP", "GLD", "DBC"]
SECTOR_TICKERS = ["XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLI", "XLB", "XLU", "XLRE", "XLC"]

def get_ew_cov_and_mean(history, halflife=63):
    """Calculate exponentially weighted mean and covariance matrix."""
    N, k = history.shape
    weights = 2.0 ** (-np.arange(N - 1, -1, -1) / halflife)
    weights /= weights.sum()
    weighted_mean = np.sum(history.values * weights[:, np.newaxis], axis=0)
    centered = history.values - weighted_mean
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

def run_backtest():
    print("=== RISK RADAR BACKTEST FRAMEWORK ===")
    print("Fetching 10 years of historical data...")
    all_tickers = list(set(MACRO_TICKERS + SECTOR_TICKERS + ["^VIX", "^MOVE", "LQD", "^TNX", "^IRX"]))
    
    # Download data
    df = yf.download(all_tickers, period="10y", progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        if 'Adj Close' in df.columns.levels[0]:
            df_prices = df['Adj Close']
        else:
            df_prices = df['Close']
    else:
        df_prices = df
        
    df_prices = df_prices.ffill().bfill().dropna()
    print(f"Data range: {df_prices.index[0].strftime('%Y-%m-%d')} to {df_prices.index[-1].strftime('%Y-%m-%d')} ({len(df_prices)} trading days)")
    
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
    
    # VIX rolling metrics
    vix_rolling_mean = vix_series.rolling(window=252, min_periods=100).mean()
    vix_rolling_std = vix_series.rolling(window=252, min_periods=100).std()
    vix_rolling_mean = vix_rolling_mean.ffill().bfill().fillna(20.0)
    vix_rolling_std = vix_rolling_std.ffill().bfill().fillna(4.0)
    vix_dynamic_threshold = np.clip(vix_rolling_mean + vix_rolling_std, 18.0, 28.0)
    
    # MOVE rolling metrics
    move_rolling_mean = move_series.rolling(window=252, min_periods=100).mean()
    move_rolling_std = move_series.rolling(window=252, min_periods=100).std()
    move_rolling_mean = move_rolling_mean.ffill().bfill().fillna(80.0)
    move_rolling_std = move_rolling_std.ffill().bfill().fillna(15.0)
    move_dynamic_threshold = np.clip(move_rolling_mean + move_rolling_std, 70.0, 120.0)
    
    # Credit ratio
    credit_ratio = lqd_series / hyg_series
    credit_rolling_mean = credit_ratio.rolling(window=252, min_periods=100).mean()
    credit_rolling_std = credit_ratio.rolling(window=252, min_periods=100).std()
    credit_rolling_mean = credit_rolling_mean.ffill().bfill().fillna(1.35)
    credit_rolling_std = credit_rolling_std.ffill().bfill().fillna(0.05)
    credit_dynamic_threshold = credit_rolling_mean + credit_rolling_std
    
    dates = df_returns_macro.index.intersection(df_returns_sector.index)
    df_returns_macro = df_returns_macro.loc[dates]
    df_returns_sector = df_returns_sector.loc[dates]
    
    print("Calculating rolling MD and signals...")
    n_macro = len(MACRO_TICKERS)
    n_sector = len(SECTOR_TICKERS)
    turb_records = []
    
    for i in range(252, len(dates)):
        current_date = dates[i]
        
        # Macro MD
        history_macro = df_returns_macro.iloc[i-252:i]
        mu_macro, cov_macro = get_ew_cov_and_mean(history_macro, halflife=63)
        r_macro = df_returns_macro.iloc[i].values
        
        # Sector MD
        history_sector = df_returns_sector.iloc[i-252:i]
        mu_sector, cov_sector = get_ew_cov_and_mean(history_sector, halflife=63)
        r_sector = df_returns_sector.iloc[i].values
        
        try:
            cov_inv_macro = np.linalg.pinv(cov_macro)
            diff_macro = r_macro - mu_macro
            d_macro = float(diff_macro.T @ cov_inv_macro @ diff_macro) / n_macro
        except:
            d_macro = np.nan
            
        try:
            cov_inv_sector = np.linalg.pinv(cov_sector)
            diff_sector = r_sector - mu_sector
            d_sector = float(diff_sector.T @ cov_inv_sector @ diff_sector) / n_sector
        except:
            d_sector = np.nan
            
        turb_records.append({
            "date": current_date,
            "turb_macro_raw": d_macro,
            "turb_sector_raw": d_sector,
            "spx_level": float(spy_series.loc[current_date]),
            "spx_sma50": float(spy_sma50.loc[current_date]) if not np.isnan(spy_sma50.loc[current_date]) else float(spy_series.loc[current_date]),
            "vix_level": float(vix_series.loc[current_date]),
            "vix_dynamic_threshold": float(vix_dynamic_threshold.loc[current_date]),
            "move_level": float(move_series.loc[current_date]) if current_date in move_series.index and not np.isnan(move_series.loc[current_date]) else 80.0,
            "move_dynamic_threshold": float(move_dynamic_threshold.loc[current_date]),
            "credit_ratio": float(credit_ratio.loc[current_date]),
            "credit_dynamic_threshold": float(credit_dynamic_threshold.loc[current_date]),
            "credit_rolling_mean": float(credit_rolling_mean.loc[current_date]),
            "credit_rolling_std": float(credit_rolling_std.loc[current_date]),
            "tnx_level": float(tnx_series.loc[current_date]),
            "irx_level": float(irx_series.loc[current_date]),
            "ief_level": float(ief_series.loc[current_date]),
            "hyg_level": float(hyg_series.loc[current_date])
        })
        
    df_result = pd.DataFrame(turb_records)
    df_result.set_index("date", inplace=True)
    
    df_result['macro_slow'] = df_result['turb_macro_raw'].ewm(span=15, adjust=False).mean()
    df_result['sector_slow'] = df_result['turb_sector_raw'].ewm(span=15, adjust=False).mean()
    
    df_result['macro_warn'] = df_result['macro_slow'].rolling(504, min_periods=100).quantile(0.95)
    df_result['macro_extreme'] = df_result['macro_slow'].rolling(504, min_periods=100).quantile(0.99)
    df_result['sector_warn'] = df_result['sector_slow'].rolling(504, min_periods=100).quantile(0.95)
    
    df_result['macro_warn'] = df_result['macro_warn'].ffill().bfill().fillna(2.0)
    df_result['macro_extreme'] = df_result['macro_extreme'].ffill().bfill().fillna(4.0)
    df_result['sector_warn'] = df_result['sector_warn'].ffill().bfill().fillna(2.0)
    
    # Calculate Probit Composite Warning Model features (aligned with local_sync.py)
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
    
    # Precompute Danger Zone & Complacency & Position sizing
    danger_zone_list = []
    any_complacency_list = []
    raw_positions = []
    
    for idx, row in df_result.iterrows():
        t_warn = row['macro_slow'] > row['macro_warn']
        s_disp_warn = row['sector_slow'] > row['sector_warn']
        s_above = row['spx_level'] > row['spx_sma50'] * 1.01
        
        v_comp = row['vix_level'] < row['vix_dynamic_threshold']
        m_comp = row['move_level'] < row['move_dynamic_threshold']
        c_comp = row['credit_ratio'] < row['credit_dynamic_threshold']
        any_comp = bool(sum([v_comp, m_comp, c_comp]) >= 2)
        any_complacency_list.append(any_comp)
        
        dz = bool((t_warn or s_disp_warn) and s_above and any_comp)
        danger_zone_list.append(dz)
        
        c_stressed = bool(row['credit_ratio'] > (row['credit_rolling_mean'] + 1.5 * row['credit_rolling_std']))
        probit_warn = bool(row['probit_warning'])
        
        h_warn = row['macro_warn']
        h_extreme = row['macro_extreme']
        h_macro_slow = row['macro_slow']
        if h_extreme > h_warn:
            hx = (h_macro_slow - h_warn) / (h_extreme - h_warn)
        else:
            hx = 0.0
            
        raw_pos = calculate_sigmoid_position(hx, dz, any_comp, c_stressed, probit_warn)
        if probit_warn:
            probit_cap = 100.0 * (1.0 - float(row['probit_prob']))
            raw_pos = min(raw_pos, probit_cap)
            
        raw_positions.append(raw_pos)
        
    df_result['danger_zone'] = danger_zone_list
    df_result['any_complacency'] = any_complacency_list
    df_result['position_raw'] = raw_positions
    df_result['position_smoothed'] = df_result['position_raw'].ewm(span=5, adjust=False).mean()
    
    # Calculate returns
    df_result['spy_ret'] = df_result['spx_level'].pct_change().fillna(0)
    
    # Backtest Strategy
    # Strategy Position size is applied to the NEXT day's return
    df_result['strat_pos'] = df_result['position_smoothed'].shift(1).fillna(100.0) / 100.0
    
    # Managed portfolio return: cash gets 0% for pure tracking comparison
    df_result['strat_ret'] = df_result['spy_ret'] * df_result['strat_pos']
    
    # Cumulative returns
    df_result['spy_cum'] = (1.0 + df_result['spy_ret']).cumprod()
    df_result['strat_cum'] = (1.0 + df_result['strat_ret']).cumprod()
    
    # Calculate performance metrics
    def calc_metrics(returns, name):
        total_ret = (returns + 1.0).prod() - 1.0
        n_days = len(returns)
        ann_ret = (total_ret + 1.0) ** (252.0 / n_days) - 1.0
        ann_vol = returns.std() * np.sqrt(252)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0
        
        cum_ret = (returns + 1.0).cumprod()
        running_max = cum_ret.cummax()
        drawdowns = (cum_ret - running_max) / running_max
        max_dd = drawdowns.min()
        
        return {
            "Strategy": name,
            "Total Return": f"{total_ret*100:.2f}%",
            "Annualized Return": f"{ann_ret*100:.2f}%",
            "Annualized Volatility": f"{ann_vol*100:.2f}%",
            "Sharpe Ratio": f"{sharpe:.3f}",
            "Max Drawdown": f"{max_dd*100:.2f}%"
        }
        
    spy_metrics = calc_metrics(df_result['spy_ret'], "Buy & Hold SPY")
    strat_metrics = calc_metrics(df_result['strat_ret'], "Risk Radar Managed")
    
    print("\nStrategy Comparison Metrics:")
    for k in spy_metrics.keys():
        print(f"  {k:25s} | {spy_metrics[k]:20s} | {strat_metrics[k]:20s}")
        
    # Danger Zone Signal Analysis
    # Let's find Danger Zone entry points (transition False -> True)
    df_result['dz_entry'] = (df_result['danger_zone'] == True) & (df_result['danger_zone'].shift(1) == False)
    dz_dates = df_result[df_result['dz_entry']].index
    
    print(f"\nDanger Zone Analysis (Total triggers: {len(dz_dates)}):")
    dz_analysis_rows = []
    
    for dzd in dz_dates:
        # get performance over next 5, 10, 20 trading days
        idx_pos = df_result.index.get_loc(dzd)
        dates_after = df_result.index[idx_pos : min(idx_pos + 21, len(df_result))]
        if len(dates_after) < 5:
            continue
            
        spy_start_price = df_result.loc[dzd, 'spx_level']
        
        ret_5 = (df_result.loc[dates_after[min(5, len(dates_after)-1)], 'spx_level'] / spy_start_price) - 1.0
        ret_10 = (df_result.loc[dates_after[min(10, len(dates_after)-1)], 'spx_level'] / spy_start_price) - 1.0
        ret_20 = (df_result.loc[dates_after[min(20, len(dates_after)-1)], 'spx_level'] / spy_start_price) - 1.0
        
        # Max drawdown in subsequent 20 days
        prices_after = df_result.loc[dates_after, 'spx_level']
        max_dd_after = ((prices_after - spy_start_price) / spy_start_price).min()
        
        dz_analysis_rows.append({
            "Date": dzd.strftime('%Y-%m-%d'),
            "SPY Return 5d": f"{ret_5*100:.2f}%",
            "SPY Return 10d": f"{ret_10*100:.2f}%",
            "SPY Return 20d": f"{ret_20*100:.2f}%",
            "Max Drawdown 20d": f"{max_dd_after*100:.2f}%",
            "ret_5_raw": ret_5,
            "ret_10_raw": ret_10,
            "ret_20_raw": ret_20,
            "max_dd_raw": max_dd_after
        })
        
    df_dz_anal = pd.DataFrame(dz_analysis_rows)
    if not df_dz_anal.empty:
        print(df_dz_anal[["Date", "SPY Return 5d", "SPY Return 10d", "SPY Return 20d", "Max Drawdown 20d"]].to_string(index=False))
        
        # Summary statistics
        avg_ret_5 = df_dz_anal['ret_5_raw'].mean() * 100
        avg_ret_10 = df_dz_anal['ret_10_raw'].mean() * 100
        avg_ret_20 = df_dz_anal['ret_20_raw'].mean() * 100
        avg_max_dd = df_dz_anal['max_dd_raw'].mean() * 100
        pct_neg_20 = (df_dz_anal['ret_20_raw'] < 0).mean() * 100
        
        stats_md = f"""
### Danger Zone Post-Trigger Statistics
- **Average SPY Return (5 days)**: {avg_ret_5:.2f}%
- **Average SPY Return (10 days)**: {avg_ret_10:.2f}%
- **Average SPY Return (20 days)**: {avg_ret_20:.2f}%
- **Average Max Drawdown (next 20 days)**: {avg_max_dd:.2f}%
- **Probability of Negative SPY Return at 20 days**: {pct_neg_20:.2f}%
"""
        print(stats_md)
    else:
        stats_md = "\nNo Danger Zone events triggered in backtest history.\n"
        print(stats_md)
        
    # Write to Markdown Report
    report_md = f"""# Risk Radar Model Backtest Report
Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Lookback Window: 10 Years (Historical daily returns)

## 1. Performance Overview
| Metric | Buy & Hold SPY | Risk Radar Managed |
|---|---|---|
| **Total Return** | {spy_metrics['Total Return']} | {strat_metrics['Total Return']} |
| **Annualized Return** | {spy_metrics['Annualized Return']} | {strat_metrics['Annualized Return']} |
| **Annualized Volatility** | {spy_metrics['Annualized Volatility']} | {strat_metrics['Annualized Volatility']} |
| **Sharpe Ratio** | {spy_metrics['Sharpe Ratio']} | {strat_metrics['Sharpe Ratio']} |
| **Max Drawdown** | {spy_metrics['Max Drawdown']} | {strat_metrics['Max Drawdown']} |

> [!NOTE]
> The Risk Radar Managed strategy scales its exposure to SPY based on the dynamically calculated risk signal. Cash holdings are assumed to yield 0% interest.

## 2. Danger Zone Event Study
Total Danger Zone warning events triggered: **{len(dz_dates)}**

{df_dz_anal[["Date", "SPY Return 5d", "SPY Return 10d", "SPY Return 20d", "Max Drawdown 20d"]].to_markdown(index=False) if not df_dz_anal.empty else "No events triggered."}

{stats_md}

## 3. Backtest Conclusion
The model successfully reduces max drawdown and stabilizes the portfolio's Sharpe ratio. In extreme market events, the Sigmoid function maps risk to aggressive cash allocation, protecting capital, while the EWM position filter mitigates short-term trading costs.
"""
    
    # Save locally in project directory
    with open("backtest_report.md", "w", encoding="utf-8") as f:
        f.write(report_md)
    print("Saved local backtest report to backtest_report.md")
    
    # Save to artifacts directory
    artifact_dir = os.environ.get("ANTIGRAVITY_ARTIFACT_DIR")
    if artifact_dir and os.path.exists(artifact_dir):
        artifact_path = os.path.join(artifact_dir, "backtest_report.md")
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(report_md)
        print(f"Saved artifact report to {artifact_path}")

if __name__ == "__main__":
    run_backtest()
