"""Same methodology as research_bot01_variants.py, applied to the mean-
reversion pivot: compare parameter variants on a chronological train/holdout
split of the cached year of BTCUSDT 5min data, so the chosen configuration
isn't just fit directly on the numbers in the committed report.
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
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion, MeanReversionParams

SYMBOL = "BTCUSDT"
GRANULARITY = "5min"

VARIANTS: dict[str, MeanReversionParams] = {
    "A_baseline (BB2.0/RSI30, no ADX filter)": MeanReversionParams(),
    "B_adx_max20 (avoid strong trends)": MeanReversionParams(adx_max=20.0),
    "C_stricter_rsi25_adx20": MeanReversionParams(rsi_oversold=25.0, adx_max=20.0),
    "D_wider_bb2.5_adx20": MeanReversionParams(bb_std=2.5, adx_max=20.0),
    "E_tighter_stop_1.0x_adx20": MeanReversionParams(atr_stop_mult=1.0, adx_max=20.0),
    "F_rsi_exit40_adx20 (exit sooner)": MeanReversionParams(rsi_exit=40.0, adx_max=20.0),
    # High-conviction stacked-filter variants: fewer trades, more confluence
    # required, aimed at cutting the trades most likely to just be noise.
    "G_volspike_adx20 (+volume climax)": MeanReversionParams(
        adx_max=20.0, volume_ratio_min=1.5,
    ),
    "H_rejection_candle_adx20 (+wick rejection)": MeanReversionParams(
        adx_max=20.0, min_close_position=0.5,
    ),
    "I_max_confluence (bb2.5/rsi25/adx15/vol1.5/rejection0.5)": MeanReversionParams(
        bb_std=2.5, rsi_oversold=25.0, adx_max=15.0,
        volume_ratio_min=1.5, min_close_position=0.5,
    ),
    "J_max_confluence_wider_stop": MeanReversionParams(
        bb_std=2.5, rsi_oversold=25.0, adx_max=15.0,
        volume_ratio_min=1.5, min_close_position=0.5,
        atr_stop_mult=2.0, atr_target_mult=4.0,
    ),
}


def fmt_row(name: str, m, split: str) -> str:
    return (
        f"{split:8s} {name:40s} trades={m.num_trades:5d}  win={m.win_rate:5.1f}%  "
        f"pf={m.profit_factor:6.3f}  exp={m.expectancy_pct:+7.3f}%  "
        f"return={m.total_return_pct:+8.2f}%  maxdd={m.max_drawdown_pct:7.2f}%"
    )


def main(days: int) -> None:
    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)

    client = BitgetPublicClient()
    df = get_or_fetch(client, SYMBOL, GRANULARITY, start_ms, end_ms)
    print(f"Loaded {len(df)} candles ({df['ts_ms'].min()} to {df['ts_ms'].max()})")

    split_idx = int(len(df) * 0.7)
    train_df, holdout_df = df.iloc[:split_idx].reset_index(drop=True), df.iloc[split_idx:].reset_index(drop=True)
    print(f"Train: {len(train_df)} bars, Holdout: {len(holdout_df)} bars\n")

    print("=== Training slice (used to pick a variant) ===")
    train_results = {}
    for name, params in VARIANTS.items():
        strategy = Bot01MeanReversion(params)
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
        strategy = Bot01MeanReversion(params)
        full = strategy.compute_indicators(holdout_df)
        result = run_backtest(strategy, full, starting_capital=1_000.0, position_fraction=0.2)
        m = compute_metrics(result)
        marker = "  <-- chosen from train" if name == best_name else ""
        print(fmt_row(name, m, "HOLDOUT") + marker)


if __name__ == "__main__":
    main(days=365)
