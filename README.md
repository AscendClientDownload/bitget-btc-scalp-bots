# bitget-btc-scalp-bots

A Bitcoin-only algorithmic scalp-trading research framework: backtesting +
**paper trading only** (no real orders placed anywhere in this repo) against
Bitget's public market-data API, with a local live dashboard.

**Read [docs/RISK_DISCLAIMER.md](docs/RISK_DISCLAIMER.md) before treating anything here as
investment advice.** Short-timeframe (1-5 minute) BTC scalping is heavily
affected by exchange fees, slippage, and market noise. A positive backtest
number is not a promise of future profit.

## What's here right now

- **Bot #1** (`src/botfarm/strategy/bot01_ema_rsi_atr.py`): EMA(9/21) trend
  cross + RSI momentum filter + volume confirmation, ATR-based stop/target,
  5-minute BTCUSDT, long-only. Fully backtested against a real year of
  Bitget history — see `reports/bot01_ema_rsi_atr/backtest_report.md`.
  **Honest result: over the last 12 months this configuration showed
  negative expectancy** (1046 trades, 20.2% win rate, profit factor 0.123,
  -0.20% average trade after fees/slippage) — it is not a working bot as
  currently tuned. That's the framework doing its job: reporting a real
  backtest result rather than a flattering fabricated one. Treat bot #1 as a
  reference implementation of the plumbing (strategy interface, cost model,
  event-driven engine, reporting) to iterate on, not as something to trade.
- A hand-written indicator library, an event-driven backtest engine with a
  realistic Bitget fee/slippage model, and performance metrics (win rate,
  Sharpe/Sortino, max drawdown, profit factor, etc.).
- A **paper-trading** 24/7 runner (`scripts/run_paper_trading.py`) and a
  local **dashboard** (`scripts/run_dashboard.py`, http://127.0.0.1:5000)
  showing live open/closed trades and summary stats.

## What's paused

The other 99 strategies (a declarative catalog) and the daily walk-forward
adaptive re-tuning module are paused at the user's request in favor of first
researching existing open-source trading bots (Freqtrade, Hummingbot, Jesse)
for strategy and dashboard ideas, and building the trades dashboard. See
`docs/ARCHITECTURE.md` for current status.

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
pytest -q
```

## Run bot #1's backtest

```powershell
python scripts/run_backtest_bot01.py --days 365
```

Writes `reports/bot01_ema_rsi_atr/backtest_report.md`, `equity_curve.png`,
and `trades.csv`. Candle data is cached in `data/raw/` so re-runs don't
re-hit the Bitget API for dates already fetched.

## Run paper trading + dashboard

```powershell
# Terminal 1
python scripts/run_paper_trading.py

# Terminal 2
python scripts/run_dashboard.py
# open http://127.0.0.1:5000
```

Both are **simulated** — `live/exchange_client.py` only reads public market
data, and `live/paper_broker.py` simulates fills using the same cost model
as the backtester. No exchange account credentials are used or needed.

## Data source

[Bitget](https://www.bitget.com)'s public spot market-data REST API
(`api.bitget.com/api/v2/spot/market/candles` and `.../history-candles`) —
no authentication required or used.
