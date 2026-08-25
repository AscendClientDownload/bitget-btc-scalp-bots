"""Start the 24/7 paper-trading runner for bot #1. Ctrl+C to stop.

This only simulates fills against Bitget's public market data — it never
places a real order. Run scripts/run_dashboard.py separately to watch trades
as they happen.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from botfarm.live.runner import run_forever
from botfarm.strategy.bot01_mean_reversion import Bot01MeanReversion

if __name__ == "__main__":
    run_forever(Bot01MeanReversion())
