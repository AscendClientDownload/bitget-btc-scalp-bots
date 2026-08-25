# Architecture

## Layout

```
src/botfarm/
├── data/        Bitget public API client + local candle cache
├── indicators/  Hand-written pandas indicators (no pandas-ta/ta-lib — see below)
├── strategy/    Strategy interface + bot #1's bespoke implementation
├── backtest/    Cost model, event-driven backtest engine, metrics, report generation
├── adaptive/    Walk-forward re-tuning (not yet built — see build order)
├── live/        Read-only exchange client, paper broker, SQLite ledger, 24/7 runner, dashboard
└── catalog/     Declarative strategy specs (paused — see project status below)
```

## Why hand-written indicators, not pandas-ta/ta-lib

`pandas-ta` is effectively unmaintained and breaks on `numpy>=1.24` (it
references the removed `numpy.NaN` attribute). `ta-lib` requires a compiled C
extension that's painful to install on Windows. Every indicator here is
plain pandas/numpy with a hand-computed-reference-value unit test in
`tests/test_indicators.py` — small dependency surface, fully auditable math.

## Why the backtest engine is hybrid vectorized + event-driven

Indicators and boolean entry/exit condition columns are computed vectorized
over the whole DataFrame (fast). But correctly simulating "skip new entry
signals while already in a trade," and deciding which of stop-loss/
take-profit fired first within a single bar, requires sequential state —
pure vectorization can't express that. So `backtest/engine.py` does one
O(n) pass after the vectorized indicator step. This is standard practice for
short-holding-period backtests and stays fast even over a year of 5-minute
bars (~105k rows).

## Why the live runner and backtester share the same Strategy code path

`strategy.compute_indicators()`, `entry_signal()`, `exit_signal()`,
`stop_loss()`, `take_profit()` are called identically by
`backtest/engine.py` and `live/runner.py`. This is deliberate: if the live
runner had its own reimplementation of the strategy logic, backtest and live
behavior could silently drift apart. There is exactly one place the
strategy's actual trading logic lives.

## The paper-trading ledger (SQLite) and dashboard

`live/ledger.py` is a small SQLite schema (`trades`, `equity_snapshots`,
`strategy_state`, `retune_log`). `live/runner.py` writes to it every tick;
`live/dashboard.py` (a local-only Flask app, `scripts/run_dashboard.py`)
reads from it and renders a live-refreshing trades table plus summary
stats (total P&L, win rate, profit factor, open positions, avg duration) —
modeled on what a well-known open-source bot's dashboard (Freqtrade's
FreqUI) surfaces for exactly this purpose. The dashboard process never
writes to the ledger.

## No live order placement

`live/exchange_client.py`'s `ExchangeClient` ABC has only read methods
(`get_recent_candles`, `get_last_price`). No implementation anywhere in this
project has an order-placement or cancellation method. `live/paper_broker.py`
simulates fills using the exact same `CostModel` as the backtester, so paper
results are directly comparable to backtest results. Adding real trading
would mean adding a new authenticated exchange client and broker — a
separate, explicit decision, not something this architecture does by
accident.

## Project status / build order

1. ✅ Repo scaffold, `data/`, `indicators/`, `strategy/`, `backtest/` — built and backtested against real Bitget history.
2. ✅ `live/` (ledger, paper broker, exchange client, 24/7 runner, dashboard) — built. Dashboard shows bot/trade cards; ledger starts empty and only fills from the live runner (an earlier smoke test pre-seeded it with backtest data, which was confusing and has been reverted — see `scripts/seed_ledger_from_backtest.py`).
3. ✅ **Bot #1 strategy search, concluded**: 15 variants across two strategy
   families (trend-following, mean-reversion — see `scripts/research_bot01_variants.py`
   and `scripts/research_mean_reversion_variants.py`) were backtested on a
   chronological train/holdout split of a full year of real Bitget 5min
   BTCUSDT data. None showed validated positive expectancy net of fees;
   expectancy consistently clustered around -0.12% to -0.20%/trade, close to
   the ~0.2-0.3% round-trip cost floor. Decision with the user: stop
   searching for a positive-expectancy variant (further attempts risk
   data-snooping — picking a "winner" out of many comparisons against the
   same data isn't evidence of real edge). Bot #1 (`bot01_mean_reversion.py`)
   ships as a reference implementation of the framework, not a profitable
   strategy.
4. ⏸ **Paused at the user's request**: the 100-strategy catalog (`catalog/`)
   and `adaptive/` walk-forward re-tuning. Resume when asked — but note the
   strategy-search finding above: an adaptive re-tuner built on top of these
   same indicator families would face the same fee-floor problem, not fix it.
