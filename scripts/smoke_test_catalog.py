"""Smoke-tests DeclarativeStrategy against real cached Bitget data for a
sample of catalog specs spanning every category -- proves the generic
engine actually runs end-to-end (indicator computation, rule evaluation,
backtest engine integration), not just unit-level correctness on synthetic
data. This is NOT a real research backtest of all 100 strategies (out of
scope per the current plan) -- just a correctness smoke test.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from botfarm.backtest.engine import run_backtest
from botfarm.backtest.metrics import compute_metrics
from botfarm.catalog.schema import load_all_specs
from botfarm.strategy.generic import DeclarativeStrategy

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "BTCUSDT_5min.csv.gz"

# One representative spec per category.
SAMPLE_IDS = [
    "tf_001_ema9_21_cross",
    "mr_001_bb_rsi_classic",
    "bo_001_donchian20_breakout",
    "mo_003_stoch_kd_cross",
    "vo_002_vwap_price_cross",
    "mi_001_ema_rsi_volume",
    "cp_001_bullish_engulfing",
    "sz_001_zscore_reversion_20",
]


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} cached candles")

    specs = {s.id: s for s in load_all_specs()}
    failures = []

    for spec_id in SAMPLE_IDS:
        spec = specs[spec_id]
        strategy = DeclarativeStrategy(spec)
        try:
            full_df = strategy.compute_indicators(df)
            result = run_backtest(strategy, full_df, starting_capital=1_000.0, position_fraction=0.2)
            metrics = compute_metrics(result)
            print(
                f"{spec_id:40s} trades={metrics.num_trades:4d}  "
                f"win={metrics.win_rate:5.1f}%  return={metrics.total_return_pct:+7.2f}%"
            )
        except Exception as e:  # noqa: BLE001
            failures.append((spec_id, e))
            print(f"{spec_id:40s} FAILED: {e}")

    if failures:
        print(f"\n{len(failures)} spec(s) failed to run:")
        for spec_id, e in failures:
            print(f"  {spec_id}: {e}")
        raise SystemExit(1)

    print(f"\nAll {len(SAMPLE_IDS)} sampled specs ran successfully end-to-end.")


if __name__ == "__main__":
    main()
