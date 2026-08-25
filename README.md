# bitget-btc-scalp-bots

A Bitcoin-only algorithmic scalp-trading research framework: backtesting +
**paper trading only** (no real orders placed anywhere in this repo) against
Bitget's public market-data API, with a local live dashboard.

**Read [docs/RISK_DISCLAIMER.md](docs/RISK_DISCLAIMER.md) before treating anything here as
investment advice.** Short-timeframe (1-5 minute) BTC scalping is heavily
affected by exchange fees, slippage, and market noise. A positive backtest
number is not a promise of future profit — and, per the research below, a
real edge from plain OHLCV technical indicators at this timeframe may not
exist at all once fees are included.

## Honest headline result

Bot #1 was iterated across **15 rigorously tested variants, two entirely
different strategy families**, each validated on genuinely out-of-sample
holdout data with Bitget's real fees (0.2% round trip):

1. **Trend-following** (EMA cross + RSI + volume, optionally +EMA100 trend
   filter, +ADX filter): 5 variants. See `reports/bot01_ema_rsi_atr/`.
2. **Mean-reversion** (Bollinger Band + RSI oversold, optionally +ADX,
   +volume-spike, +rejection-candle confluence): 10 variants. See
   `reports/bot01_mean_reversion/` and `scripts/research_mean_reversion_variants.py`.

**None showed a validated positive edge.** Expectancy per trade consistently
clustered around -0.12% to -0.20% — right around the transaction cost floor —
regardless of indicator logic. Stacking many confirming filters at once
("maximum confluence") didn't fix it either; it just multiplied several
independently-rare conditions together until the strategy stopped producing
any trades at all (0 trades across a full year). That's a real, converging
finding: **at 5-minute BTCUSDT, Bitget's fees are a bigger factor than which
indicators you use.**

Decision (with the user): stop searching for a positive-expectancy variant
via more indicator permutations — every additional variant tested against
the same year of data raises the risk that any eventual "winner" is luck
(data-snooping), not real edge. Bot #1 ships as a working **reference
implementation** of the framework, not a profitable strategy.

## What's here right now

- **Bot #1** (`src/botfarm/strategy/bot01_mean_reversion.py`, class
  `Bot01MeanReversion`): Bollinger Band + RSI oversold entry with an
  ADX<=20 "don't fight a strong trend" filter, ATR-based stop, 5-minute
  BTCUSDT, long-only. Backtested against a real year of Bitget history —
  see `reports/bot01_mean_reversion/backtest_report.md` (170 trades, 34.7%
  win rate, profit factor 0.38, still net negative — reported as-is).
  An earlier trend-following version (`bot01_ema_rsi_atr.py`) is kept in the
  repo as a documented, tested dead end — see the research above.
- A hand-written indicator library (including ADX/DMI), an event-driven
  backtest engine with a realistic Bitget fee/slippage model, and
  performance metrics (win rate, Sharpe/Sortino, max drawdown, profit
  factor, etc.).
- A **paper-trading** 24/7 runner (`scripts/run_paper_trading.py`, $1,000
  starting capital) and a local **dashboard** (`scripts/run_dashboard.py`,
  http://127.0.0.1:5000) showing live open/closed trades as cards, plus
  summary stats. The ledger starts genuinely empty — it is not pre-seeded
  with backtest data (that caused real confusion once during development;
  see `scripts/seed_ledger_from_backtest.py`'s docstring).

## What's paused

The other 99 strategies (a declarative catalog) and the daily walk-forward
adaptive re-tuning module are paused. See `docs/ARCHITECTURE.md` for current
status.

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

Writes `reports/bot01_mean_reversion/backtest_report.md`, `equity_curve.png`,
and `trades.csv`. Candle data is cached in `data/raw/` so re-runs don't
re-hit the Bitget API for dates already fetched.

To see the full variant-comparison research behind the current defaults:

```powershell
python scripts/research_bot01_variants.py            # trend-following, 5 variants
python scripts/research_mean_reversion_variants.py   # mean-reversion, 10 variants
```

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
