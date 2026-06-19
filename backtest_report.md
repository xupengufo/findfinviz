# Risk Radar Model Backtest Report
Created: 2026-06-19 19:53:28
Lookback Window: 10 Years (Historical daily returns)

## 1. Performance Overview
| Metric | Buy & Hold SPY | Risk Radar Managed |
|---|---|---|
| **Total Return** | 250.01% | 248.52% |
| **Annualized Return** | 14.97% | 14.92% |
| **Annualized Volatility** | 18.68% | 15.53% |
| **Sharpe Ratio** | 0.801 | 0.961 |
| **Max Drawdown** | -33.72% | -24.67% |

> [!NOTE]
> The Risk Radar Managed strategy scales its exposure to SPY based on the dynamically calculated risk signal. Cash holdings are assumed to yield 0% interest.

## 2. Danger Zone Event Study
Total Danger Zone warning events triggered: **12**

| Date       | SPY Return 5d   | SPY Return 10d   | SPY Return 20d   | Max Drawdown 20d   |
|:-----------|:----------------|:-----------------|:-----------------|:-------------------|
| 2017-07-05 | 0.51%           | 1.74%            | 1.92%            | -0.91%             |
| 2017-11-06 | -0.20%          | -0.21%           | 1.68%            | -0.93%             |
| 2017-11-16 | 0.67%           | 2.26%            | 3.58%            | -0.29%             |
| 2017-11-30 | -0.35%          | 0.25%            | 1.21%            | -0.69%             |
| 2018-02-01 | -8.51%          | -3.04%           | -4.44%           | -8.51%             |
| 2018-07-06 | 1.51%           | 1.55%            | 2.97%            | 0.00%              |
| 2024-07-16 | -1.96%          | -4.05%           | -4.04%           | -8.41%             |
| 2024-07-31 | -5.84%          | -1.28%           | 1.36%            | -6.07%             |
| 2024-09-26 | -0.78%          | 0.67%            | 1.21%            | -0.79%             |
| 2024-11-06 | 1.04%           | -0.09%           | 2.64%            | -0.90%             |
| 2025-01-28 | -0.45%          | 0.13%            | -1.65%           | -1.70%             |
| 2026-02-09 | -1.60%          | -0.95%           | -2.42%           | -3.11%             |


### Danger Zone Post-Trigger Statistics
- **Average SPY Return (5 days)**: -1.33%
- **Average SPY Return (10 days)**: -0.25%
- **Average SPY Return (20 days)**: 0.34%
- **Average Max Drawdown (next 20 days)**: -2.69%
- **Probability of Negative SPY Return at 20 days**: 33.33%


## 3. Backtest Conclusion
The model successfully reduces max drawdown and stabilizes the portfolio's Sharpe ratio. In extreme market events, the Sigmoid function maps risk to aggressive cash allocation, protecting capital, while the EWM position filter mitigates short-term trading costs.
