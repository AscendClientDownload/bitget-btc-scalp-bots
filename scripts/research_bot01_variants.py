"""Compare bot #1 parameter variants on a chronological train/holdout split,
so the final chosen configuration isn't just fit directly on the exact
numbers reported in reports/bot01_ema_rsi_atr/ (that would be curve-fitting,
not honest backtesting).

Train = first 70% of the cached year of data, holdout = last 30%, split by
time (never shuffled) so holdout is genuinely out-of-sample.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.backtest.engine import run_backtest
from botfarm.backtest.metrics import compute_metrics
from botfarm.data.bitget_client import BitgetPublicClient
from botfarm.data.cache import get_or_fetch
from botfarm.strategy.bot01_ema_rsi_atr import Bot01EmaRsiAtr, Bot01Params

SYMBOL = "BTCUSDT"
GRANULARITY = "5min"

VARIANTS: dict[str, Bot01Params] = {
    "A_baseline (no filters, tight stop)": Bot01Params(),
    "B_trend_filter (+EMA100)": Bot01Params(trend_ema_period=100),
    "C_trend_and_adx (+EMA100, +ADX>=20)": Bot01Params(trend_ema_period=100, adx_min=20.0),
    "D_trend_adx_wider_stop (+1.5xATR/2.5xATR)": Bot01Params(
        trend_ema_period=100, adx_min=20.0, atr_stop_mult=1.5, atr_target_mult=2.5
    ),
    "E_trend_adx_stricter_rsi": Bot01Params(
        trend_ema_period=100, adx_min=25.0, atr_stop_mult=1.5, atr_target_mult=2.5,
        rsi_low=55.0, rsi_high=68.0,
    ),
}


def fmt_row(name: str, m, split: str) -> str:
    return (
        f"{split:8s} {name:45s} trades={m.num_trades:5d}  win={m.win_rate:5.1f}%  "
        f"pf={m.profit_factor:6.3f}  exp={m.expectancy_pct:+7.3f}%  "
        f"return={m.total_return_pct:+8.2f}%  maxdd={m.max_drawdown_pct:7.2f}%"
    )


def main(days: int) -> None:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    client = BitgetPublicClient()
    df = get_or_fetch(client, SYMBOL, GRANULARITY, start_ms, end_ms)
    print(f"Loaded {len(df)} candles from cache/API ({df['ts_ms'].min()} to {df['ts_ms'].max()})")

    split_idx = int(len(df) * 0.7)
    train_df, holdout_df = df.iloc[:split_idx].reset_index(drop=True), df.iloc[split_idx:].reset_index(drop=True)
    print(f"Train: {len(train_df)} bars, Holdout: {len(holdout_df)} bars\n")

    print("=== Training slice (used to pick a variant) ===")
    train_results = {}
    for name, params in VARIANTS.items():
        strategy = Bot01EmaRsiAtr(params)
        full = strategy.compute_indicators(train_df)
        result = run_backtest(strategy, full, starting_capital=1_000.0, position_fraction=0.2)
        m = compute_metrics(result)
        train_results[name] = m
        print(fmt_row(name, m, "TRAIN"))

    best_name = max(
        train_results,
        key=lambda n: (train_results[n].expectancy_pct if train_results[n].num_trades >= 20 else -999),
    )
    print(f"\nBest on train (min 20 trades, highest expectancy): {best_name}\n")

    print("=== Holdout slice (out-of-sample validation of ALL variants, for transparency) ===")
    for name, params in VARIANTS.items():
        strategy = Bot01EmaRsiAtr(params)
        full = strategy.compute_indicators(holdout_df)
        result = run_backtest(strategy, full, starting_capital=1_000.0, position_fraction=0.2)
        m = compute_metrics(result)
        marker = "  <-- chosen from train" if name == best_name else ""
        print(fmt_row(name, m, "HOLDOUT") + marker)


if __name__ == "__main__":
    main(days=365)
