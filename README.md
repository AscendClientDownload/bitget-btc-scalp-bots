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

## The 100-strategy catalog

`STRATEGY_CATALOG.md` has all 100 — 8 categories (trend-following,
mean-reversion, breakout/volatility, momentum/oscillator, volume/order-flow,
multi-indicator confluence, candlestick pattern, statistical/z-score), each a
genuinely distinct rule, not a bare parameter sweep. They're declarative YAML
specs (`src/botfarm/catalog/specs/`) interpreted at runtime by
`DeclarativeStrategy` (`src/botfarm/strategy/generic.py`) through a
**restricted AST-based expression evaluator** (`strategy/safe_eval.py` — no
`eval()`, no function calls, no attribute access, just a whitelisted set of
comparison/boolean/arithmetic nodes) — so any spec runs through the exact
same backtest/live engine as bot #1 without bespoke code per strategy.
Correctness was cross-checked by reproducing bot #1's exact logic as a
catalog spec (`mi_001_ema_rsi_volume`) and confirming it produces the
identical backtest result (-46.58% return) as the original bespoke
implementation.

**Important**: none of the 100 have been individually backtested for edge —
only a sample (one per category) was smoke-tested to confirm the engine runs
them correctly, not that any are profitable. Given bot #1's 15-variant
finding (see `docs/RISK_DISCLAIMER.md`), assume the same fee-floor problem
applies here until an actual backtest says otherwise. Regenerate the catalog
via `python scripts/generate_strategy_catalog.py` (rewrites the YAML specs)
and `python -c "from botfarm.catalog.generate_catalog_md import main; main()"`
(rewrites `STRATEGY_CATALOG.md`).

The daily walk-forward adaptive re-tuning module is still paused — see
`docs/ARCHITECTURE.md` for status.

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

### Running it persistently, option A: your own PC (survives closing the terminal)

`scripts/service/run_paper_trading_forever.ps1` and `run_dashboard_forever.ps1`
wrap each process in an auto-restart loop and log to `logs/`. A launcher at
`shell:startup` (`BotFarmAutostart.vbs`, machine-local, not part of this repo)
runs both hidden at every Windows logon — real Task Scheduler registration
was tried first but failed with Access Denied in this environment, so the
Startup folder is the actual mechanism in use. This still requires the PC to
be on and you logged in; it is not the same as cloud hosting.

### Running it persistently, option B: cloud hosting (no PC dependency) — on hold

A Railway deployment was attempted and abandoned: the paper-trading bot ran
there successfully (volume mounted, ticking correctly every 5 minutes), but
the dashboard/web process returned a persistent 502 with no diagnosable
cause after extensive log-level troubleshooting — plausibly a stuck/stale
deploy not actually picking up the latest pushed commits, never confirmed.
The Railway-specific files (`Procfile`, `scripts/railway_start.py`,
`docs/DEPLOY_RAILWAY.md`) have been removed. Two things from that attempt
are kept because they're generic, not Railway-specific, and will be needed
again for whatever host comes next: `dashboard.py` binds to `0.0.0.0` on
whatever `$PORT` is injected (falling back to `127.0.0.1:5000` for local
dev) and uses `waitress` as a production server when `$PORT` is present;
`ledger.py`'s `DB_PATH` respects a `BOTFARM_DB_PATH` env var override for
pointing the SQLite file at a mounted persistent volume.

Other options evaluated and why they don't fit a free/no-card always-on
background worker (see `docs/ARCHITECTURE.md`): Vercel/Cloud Run don't
support a persistent background process at all; Render has no background
workers on its free tier at all (not just a sleep issue); Koyeb's free tier
scales to zero on idle; Fly.io's free allowance is essentially gone; GCP
`e2-micro` / Oracle Ampere A1 are genuinely permanent free VMs but require a
credit card for identity verification during signup.

## Data source

[Bitget](https://www.bitget.com)'s public spot market-data REST API
(`api.bitget.com/api/v2/spot/market/candles` and `.../history-candles`) —
no authentication required or used.
