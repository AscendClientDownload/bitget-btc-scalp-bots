"""Runs bot01 plus all 100 catalog strategies live (paper trading only) in
one process. Each strategy gets its own $1,000 starting capital, tracked
independently in the ledger by strategy_id -- the dashboard already
supports showing many bots since strategy_state is keyed that way.

None of the 100 catalog strategies have been backtested for edge (only
smoke-tested for correctness) -- see STRATEGY_CATALOG.md and
docs/RISK_DISCLAIMER.md. Running them live (paper) is a way to observe them,
not a claim that any of them work.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.catalog.schema import load_all_specs
from botfarm.live.runner import run_forever_multi
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion
from botfarm.strategy.generic import DeclarativeStrategy

if __name__ == "__main__":
    specs = load_all_specs()
    strategies = [Bot01MeanReversion()] + [DeclarativeStrategy(spec) for spec in specs]
    print(f"Loaded {len(strategies)} strategies (bot01 + {len(specs)} catalog specs)")
    run_forever_multi(strategies)
