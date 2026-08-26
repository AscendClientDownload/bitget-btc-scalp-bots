"""Backtests all 100 catalog strategies against a full year of real cached
Bitget data -- unlike the earlier 8-sample smoke test (which only proved the
engine runs without crashing), this produces real per-strategy statistics
(hundreds-thousands of trades each) that can actually be used to judge which
strategies are relatively better or worse, instead of reacting to the 1-3
live trades each bot has accumulated so far.

Writes results to reports/full_catalog_backtest.csv and prints a ranked
summary. Does NOT retune/modify any strategy parameters -- this is
measurement only, a prerequisite for any real "make them better" decision.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from botfarm.backtest.engine import run_backtest
from botfarm.backtest.metrics import compute_metrics
from botfarm.catalog.schema import load_all_specs
from botfarm.strategy.generic import DeclarativeStrategy

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "raw" / "BTCUSDT_5min.csv.gz"
OUT_PATH = Path(__file__).resolve().parents[1] / "reports" / "full_catalog_backtest.csv"


def main() -> None:
    df = pd.read_csv(DATA_PATH)
    print(f"Loaded {len(df)} cached candles", flush=True)

    specs = load_all_specs()
    print(f"Backtesting {len(specs)} catalog strategies...", flush=True)

    rows = []
    start = time.monotonic()
    for i, spec in enumerate(specs, 1):
        strategy = DeclarativeStrategy(spec)
        try:
            full_df = strategy.compute_indicators(df)
            result = run_backtest(strategy, full_df, starting_capital=1_000.0, position_fraction=0.2)
            m = compute_metrics(result)
            rows.append({
                "id": spec.id, "category": spec.category, "trades": m.num_trades,
                "win_rate_pct": round(m.win_rate, 2), "profit_factor": round(m.profit_factor, 4),
                "expectancy_pct": round(m.expectancy_pct, 4), "total_return_pct": round(m.total_return_pct, 2),
                "max_drawdown_pct": round(m.max_drawdown_pct, 2), "sharpe": round(m.sharpe, 3),
                "error": "",
            })
        except Exception as e:  # noqa: BLE001
            rows.append({
                "id": spec.id, "category": spec.category, "trades": 0, "win_rate_pct": 0,
                "profit_factor": 0, "expectancy_pct": 0, "total_return_pct": 0,
                "max_drawdown_pct": 0, "sharpe": 0, "error": str(e),
            })
        elapsed = time.monotonic() - start
        print(f"[{i}/{len(specs)}] {spec.id:45s} trades={rows[-1]['trades']:5d} "
              f"exp={rows[-1]['expectancy_pct']:+7.3f}%  ({elapsed:.0f}s elapsed)", flush=True)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    valid = [r for r in rows if not r["error"] and r["trades"] >= 20]
    valid.sort(key=lambda r: r["expectancy_pct"], reverse=True)

    positive = [r for r in valid if r["expectancy_pct"] > 0]
    print(f"\n=== Done. {len(rows)} strategies backtested, {len(valid)} with >=20 trades. ===")
    print(f"Strategies with POSITIVE expectancy (min 20 trades): {len(positive)}")
    print("\nTop 10 by expectancy:")
    for r in valid[:10]:
        print(f"  {r['id']:45s} trades={r['trades']:5d} win={r['win_rate_pct']:5.1f}% "
              f"pf={r['profit_factor']:6.3f} exp={r['expectancy_pct']:+7.3f}% return={r['total_return_pct']:+8.2f}%")
    print("\nBottom 10 by expectancy:")
    for r in valid[-10:]:
        print(f"  {r['id']:45s} trades={r['trades']:5d} win={r['win_rate_pct']:5.1f}% "
              f"pf={r['profit_factor']:6.3f} exp={r['expectancy_pct']:+7.3f}% return={r['total_return_pct']:+8.2f}%")
    print(f"\nFull results: {OUT_PATH}")


if __name__ == "__main__":
    main()
