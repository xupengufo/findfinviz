# Risk Radar Model Backtest Report
Created: 2026-06-19 22:34:20
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

## 2. Probit Warning Event Study
Total Probit warning events triggered: **16**

| Date       |   Probit P | SPY Return 5d   | SPY Return 10d   | SPY Return 20d   | Max Drawdown 20d   |
|:-----------|-----------:|:----------------|:-----------------|:-----------------|:-------------------|
| 2020-02-27 |       0.47 | 1.66%           | -16.60%          | -11.69%          | -24.62%            |
| 2020-03-03 |       0.33 | -3.94%          | -15.80%          | -13.65%          | -25.31%            |
| 2020-03-05 |       0.41 | -17.97%         | -20.48%          | -16.25%          | -25.85%            |
| 2020-03-25 |       0.37 | -0.26%          | 11.04%           | 13.08%           | -0.26%             |
| 2022-04-26 |       0.3  | 0.07%           | -4.09%           | -5.34%           | -6.40%             |
| 2022-04-29 |       0.32 | -0.16%          | -2.50%           | 0.79%            | -5.47%             |
| 2022-05-09 |       0.37 | 0.48%           | -0.31%           | 4.41%            | -2.19%             |
| 2024-08-05 |       0.39 | 3.07%           | 8.16%            | 6.71%            | 0.00%              |
| 2024-10-31 |       0.34 | 4.74%           | 4.35%            | 5.96%            | 0.00%              |
| 2024-12-18 |       0.63 | 2.91%           | 1.31%            | 3.21%            | -0.65%             |
| 2025-01-10 |       0.33 | 2.94%           | 3.25%            | 4.20%            | 0.00%              |
| 2025-03-03 |       0.32 | -3.97%          | -2.85%           | -3.89%           | -5.54%             |
| 2025-03-06 |       0.42 | -3.72%          | -1.26%           | -6.01%           | -6.01%             |
| 2025-04-03 |       0.57 | -2.26%          | -1.92%           | 5.60%            | -7.49%             |
| 2026-03-06 |       0.32 | -1.50%          | -3.28%           | -1.73%           | -5.75%             |
| 2026-03-27 |       0.37 | 3.92%           | 8.20%            | 12.79%           | -0.33%             |


### Probit Warning Post-Trigger Statistics
- **Average SPY Return (5 days)**: -0.87%
- **Average SPY Return (10 days)**: -2.05%
- **Average SPY Return (20 days)**: -0.11%
- **Average Max Drawdown (next 20 days)**: -7.24%
- **Probability of Negative SPY Return at 20 days**: 43.75%


## 3. Backtest Conclusion
P0-4 update: the risk state is now driven purely by the Probit crash-probability model (VIX + yield curve + credit spread), replacing the old 6-signal Danger Zone composite whose 20-day negative-return hit rate was only 33%. The Sigmoid position-sizing still uses macro turbulence distance + complacency + credit stress as inputs, with a Probit-probability cap on max exposure.
