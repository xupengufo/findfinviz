# Risk Radar Model Backtest Report
Created: 2026-06-09 09:41:00
Lookback Window: 10 Years (Historical daily returns)

## 1. Performance Overview
| Metric | Buy & Hold SPY | Risk Radar Managed |
|---|---|---|
| **Total Return** | 250.23% | 253.04% |
| **Annualized Return** | 14.99% | 15.09% |
| **Annualized Volatility** | 18.66% | 16.28% |
| **Sharpe Ratio** | 0.803 | 0.927 |
| **Max Drawdown** | -33.72% | -24.70% |

> [!NOTE]
> The Risk Radar Managed strategy scales its exposure to SPY based on the dynamically calculated risk signal. Cash holdings are assumed to yield 0% interest.

## 2. Danger Zone Event Study
Total Danger Zone warning events triggered: **10**

| Date       | SPY Return 5d   | SPY Return 10d   | SPY Return 20d   | Max Drawdown 20d   |
|:-----------|:----------------|:-----------------|:-----------------|:-------------------|
| 2017-07-05 | 0.51%           | 1.74%            | 1.92%            | -0.91%             |
| 2017-11-16 | 0.67%           | 2.26%            | 3.58%            | -0.29%             |
| 2017-11-30 | -0.35%          | 0.25%            | 1.21%            | -0.69%             |
| 2018-02-02 | -5.06%          | -0.85%           | -1.18%           | -6.47%             |
| 2024-07-16 | -1.96%          | -4.05%           | -4.04%           | -8.41%             |
| 2024-07-31 | -5.84%          | -1.28%           | 1.36%            | -6.07%             |
| 2024-09-26 | -0.78%          | 0.67%            | 1.21%            | -0.79%             |
| 2024-11-06 | 1.04%           | -0.09%           | 2.64%            | -0.90%             |
| 2025-01-28 | -0.45%          | 0.13%            | -1.65%           | -1.70%             |
| 2026-02-09 | -1.60%          | -0.95%           | -2.42%           | -3.11%             |


### Danger Zone Post-Trigger Statistics
- **Average SPY Return (5 days)**: -1.38%
- **Average SPY Return (10 days)**: -0.22%
- **Average SPY Return (20 days)**: 0.26%
- **Average Max Drawdown (next 20 days)**: -2.93%
- **Probability of Negative SPY Return at 20 days**: 40.00%


## 3. Backtest Conclusion
The model successfully reduces max drawdown and stabilizes the portfolio's Sharpe ratio. In extreme market events, the Sigmoid function maps risk to aggressive cash allocation, protecting capital, while the EWM position filter mitigates short-term trading costs.
