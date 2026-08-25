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
4. ✅ **100-strategy catalog, built**: `catalog/schema.py` defines
   `StrategySpec` (YAML-loaded, validated); `strategy/safe_eval.py` is a
   restricted AST-walking expression evaluator (whitelisted node types only —
   no `eval()`, no calls, no attribute/subscript access) for entry/exit rule
   strings; `strategy/generic.py`'s `DeclarativeStrategy` interprets a spec
   through an indicator registry covering every indicator in `indicators/`,
   plus a `cross_above`/`cross_below` special-cased pair for crossover rules
   (vectorized `.shift()` comparison, since the row-at-a-time rule evaluator
   can't itself express "crossed" without a precomputed boolean column) and
   auto-computed helper columns (`prev_open`/`prev_close`/etc., `_atr`) so
   candlestick-pattern and ATR-stop rules work without per-spec boilerplate.
   `scripts/generate_strategy_catalog.py` defines and writes all 100 specs
   (8 categories, each a genuinely distinct rule); `catalog/generate_catalog_md.py`
   renders `STRATEGY_CATALOG.md` from them. Correctness cross-check: one spec
   (`mi_001_ema_rsi_volume`) reproduces bot #1's exact original logic and
   was confirmed to produce an identical backtest result (-46.58% return) to
   the bespoke `Bot01EmaRsiAtr` implementation. `scripts/smoke_test_catalog.py`
   runs one spec per category against real cached data to confirm the engine
   works end-to-end — this is a correctness smoke test, not a real backtest;
   none of the 100 have been individually backtested for edge (see the
   strategy-search finding above — assume the same fee-floor problem applies
   until proven otherwise).
5. ⏸ **Still paused**: `adaptive/` walk-forward re-tuning. Resume when
   asked — note it would face the same fee-floor problem the strategy search
   found, not fix it.
6. ✅ **Persistence**: the runner and dashboard need to survive closing
   Claude Code / this terminal to be genuinely 24/7. Two mechanisms were
   tried:
   - `Register-ScheduledTask` / `schtasks.exe` (real Windows Task Scheduler)
     — **failed with Access Denied** in this environment even with the
     sandbox restriction lifted; not just an admin-rights issue, something
     about this session's account can't touch Task Scheduler at all.
   - **Windows Startup folder** (`shell:startup`) — works with a normal file
     write, no elevated permissions needed. A `.vbs` launcher there
     (`BotFarmAutostart.vbs`, outside the repo — it's machine config, not
     project code) runs both `scripts/service/run_*_forever.ps1` wrapper
     scripts hidden at every logon. Each wrapper loops forever, restarting
     the underlying Python process if it crashes, logging to `logs/`.
   - **Caveat this doesn't solve**: the PC still needs to be on and the user
     logged in. True always-on-regardless-of-PC needs a cloud host — no free
     option is both real (persistent, not scale-to-zero like Vercel/Cloud
     Run) and simple; GCP's `e2-micro` and Oracle's Ampere A1 are the two
     genuinely-permanent-free VM tiers as of Aug 2026, but both require the
     user to create the cloud account/VM themselves (identity + billing
     verification only they can do) before any remote setup can happen.
7. ❌ **Railway deployment, attempted and abandoned**: chosen over GCP/Oracle
   to avoid a credit card requirement. The bot side worked correctly (volume
   mounted, ticking every 5 minutes, confirmed via deploy logs). The
   dashboard/web process returned a persistent 502 with no diagnosable cause
   despite extensive log-level troubleshooting (explicit print diagnostics
   at every stage of startup showed nothing past the ledger import — most
   likely a stale/stuck deploy not actually running the latest pushed
   commits, but this was never confirmed since the user couldn't locate a
   working "redeploy latest commit" control). `Procfile`,
   `scripts/railway_start.py`, and `docs/DEPLOY_RAILWAY.md` were removed at
   the user's request. Kept because they're generic, not Railway-specific:
   `dashboard.py`'s `$PORT`/`0.0.0.0`/`waitress` handling (falls back to
   `127.0.0.1:5000` + Flask's dev server with no `$PORT` set) and
   `ledger.py`'s `BOTFARM_DB_PATH` override for a mounted persistent volume
   — both needed again for whatever host comes next. A quick survey of
   alternatives (Render: no background workers on free tier at all; Koyeb:
   scales to zero on idle; Fly.io: free allowance essentially gone) found
   nothing else free+simple+truly-always-on either — revisit when the user
   wants to try hosting again.
