# Backtest Report: bot01_mean_reversion

- **Symbol**: BTCUSDT
- **Timeframe**: 5min
- **Date range**: 2025-08-25 to 2026-08-25
- **Starting capital**: 1,000.00
- **Ending capital**: 918.53

## Metrics

| Metric | Value |
|---|---|
| Total return | -8.15% |
| Number of trades | 170 |
| Win rate | 34.71% |
| Profit factor | 0.382 |
| Max drawdown | -8.15% |
| Sharpe (annualized) | -7.681 |
| Sortino (annualized) | -1.109 |
| Avg trade return | -0.150% |
| Avg holding bars | 5.9 |
| Expectancy per trade | -0.150% |

## Verdict

**Negative expectancy over this period** (profit factor 0.382, expectancy -0.150% per trade). This configuration did not show a real edge net of fees and slippage over the tested window. Do not treat this as a working bot — see docs/RISK_DISCLAIMER.md.

## Notes / assumptions

- Fees: Bitget spot taker rate (0.1% per side, 0.2% round trip).
- Slippage: fixed 5bps haircut against the trader per fill (assumption, not measured market impact).
- One position at a time, fixed-fractional sizing, long-only (spot).
- Past backtest performance on historical data does not guarantee future results. Short-timeframe (1-5min) BTC scalping is heavily affected by fees, slippage, and market noise — see docs/RISK_DISCLAIMER.md.
