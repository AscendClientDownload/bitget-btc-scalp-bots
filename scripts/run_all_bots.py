"""Runs bot01 plus a curated subset of the catalog strategies live (paper
trading only) in one process. Each strategy gets its own $1,000 starting
capital, tracked independently in the ledger by strategy_id.

Originally ran all 100 catalog strategies live. After running a real
full-year backtest of all 100 (scripts/backtest_full_catalog.py,
reports/full_catalog_backtest.csv), 0 of them showed positive expectancy
with a statistically meaningful trade count -- so "running all 100" wasn't
adding information, just noise and capital drain on ~80 strategies already
known to be clearly worse than the rest. ACTIVE_STRATEGY_IDS below is the
top 15 by backtested expectancy (min 20 trades in the backtest), chosen
directly from that CSV, not a guess. None of these are profitable either --
they're just the least-bad -- see docs/RISK_DISCLAIMER.md.

Pass --all to run the full 100 anyway (e.g. to regenerate the backtest CSV
or watch the pruned-out strategies for some other reason).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.catalog.schema import load_all_specs
from botfarm.live.runner import run_forever_multi
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion
from botfarm.strategy.generic import DeclarativeStrategy

# Top 15 catalog strategies by expectancy_pct from reports/full_catalog_backtest.csv
# (min 20 trades over the full-year backtest), highest (least-bad) first.
ACTIVE_STRATEGY_IDS = [
    "mr_006_bb_rsi_adx_filter",
    "cp_001_bullish_engulfing",
    "cp_009_gap_up_continuation",
    "sz_008_zscore_extreme_adx_filter",
    "vo_005_vwap_dip_volume",
    "sz_002_zscore_reversion_10",
    "sz_003_zscore_reversion_30",
    "mi_010_bb_stoch_adx_mr",
    "sz_011_zscore_overshoot_exit",
    "mr_013_zscore_short_window",
    "tf_001_ema9_21_cross",
    "sz_005_zscore_volume_confirm",
    "vo_010_volume_climax_reversal",
    "mr_010_bb_volume_climax",
    "mr_005_percent_b_reversion",
]

if __name__ == "__main__":
    run_all = "--all" in sys.argv
    specs = load_all_specs()
    if not run_all:
        by_id = {s.id: s for s in specs}
        missing = [sid for sid in ACTIVE_STRATEGY_IDS if sid not in by_id]
        if missing:
            raise SystemExit(f"ACTIVE_STRATEGY_IDS references unknown spec ids: {missing}")
        specs = [by_id[sid] for sid in ACTIVE_STRATEGY_IDS]

    strategies = [Bot01MeanReversion()] + [DeclarativeStrategy(spec) for spec in specs]
    print(f"Loaded {len(strategies)} strategies (bot01 + {len(specs)} catalog specs, "
          f"{'full catalog' if run_all else 'pruned to top performers by backtested expectancy'})")
    run_forever_multi(strategies)
